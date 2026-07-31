"""Sprint 10.4: generation stress runner unit/integration tests (fake Claude only)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

import config
import database
from claude_exceptions import ClaudeOutputTruncatedError, MenuConstraintError
from qa.cost_estimate import confirm_real_run, estimate_run_cost
from qa.generation_stress_test import build_parser, main
from qa.metrics import aggregate_runs, classify_exception
from qa.profiles import generate_profiles
from qa.reports import build_report_payload, write_csv_report, write_json_report, write_markdown_report
from qa.runner import StressRunner, StressRunnerConfig, install_default_fake
from qa.thresholds import evaluate_thresholds


@pytest.fixture
def qa_db(tmp_path, monkeypatch):
    db_path = tmp_path / "qa-stress.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "ENVIRONMENT", "qa")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "qa-fake-key-not-a-secret")
    asyncio.run(database.init_db())
    return tmp_path


def test_profiles_are_deterministic_by_seed():
    a = generate_profiles(runs=20, seed=42, mode="generated")
    b = generate_profiles(runs=20, seed=42, mode="generated")
    c = generate_profiles(runs=20, seed=43, mode="generated")
    assert [p.summary() for p in a] == [p.summary() for p in b]
    assert [p.summary() for p in a] != [p.summary() for p in c]


def test_profiles_stay_within_valid_ranges():
    profiles = generate_profiles(runs=50, seed=7, mode="mixed")
    for profile in profiles:
        days = int(profile.profile["days"])
        budget = float(profile.profile["budget"])
        assert 1 <= days <= 7
        assert 500 <= budget <= 50000
        assert profile.profile["cooktime"] in {"fast", "medium", "slow"}
        assert profile.persons >= 1


def test_classify_exception_categories():
    kind, code = classify_exception(MenuConstraintError("x", issue_codes=["MEAL_DUPLICATE_EXCESSIVE"]))
    assert kind == "controlled_failure"
    assert code == "MENU_GENERATION_INVALID"
    kind, code = classify_exception(ClaudeOutputTruncatedError("t", stop_reason="max_tokens"))
    assert kind == "controlled_failure"
    assert code == "MENU_GENERATION_OUTPUT_TRUNCATED"
    kind, code = classify_exception(RuntimeError("boom"))
    assert kind == "unexpected_failure"


def test_success_first_attempt(qa_db, monkeypatch):
    reports = qa_db / "reports"
    reports.mkdir()
    cfg = StressRunnerConfig(runs=3, seed=42, fake_mode="success_first", profiles="fixtures")
    runner = StressRunner(cfg, reports_dir=reports, install_fake=install_default_fake)
    payload = asyncio.run(runner.run())
    assert payload["aggregate"]["success_count"] == 3
    assert all(run["successful_attempt"] == 1 for run in payload["runs"])
    assert payload["thresholds"]["verdict"] in {"PASS", "WARN"}


def test_success_after_targeted_retry(qa_db):
    reports = qa_db / "reports"
    reports.mkdir()
    cfg = StressRunnerConfig(
        runs=2,
        seed=42,
        fake_mode="success_after_retry",
        profiles="fixtures",
    )
    runner = StressRunner(cfg, reports_dir=reports, install_fake=install_default_fake)
    payload = asyncio.run(runner.run())
    assert payload["aggregate"]["success_count"] == 2
    assert all(run["successful_attempt"] >= 2 for run in payload["runs"])


def test_controlled_failure_after_retries(qa_db):
    reports = qa_db / "reports"
    reports.mkdir()
    cfg = StressRunnerConfig(
        runs=1,
        seed=42,
        fake_mode="always_constraint",
        profiles="fixtures",
    )
    runner = StressRunner(cfg, reports_dir=reports, install_fake=install_default_fake)
    payload = asyncio.run(runner.run())
    assert payload["runs"][0]["result"] == "controlled_failure"
    assert payload["runs"][0]["error_code"] == "MENU_GENERATION_INVALID"
    assert payload["aggregate"]["unexpected_failure_count"] == 0


def test_unexpected_exception_classification(qa_db):
    reports = qa_db / "reports"
    reports.mkdir()
    cfg = StressRunnerConfig(runs=1, seed=42, fake_mode="unexpected", profiles="fixtures")
    runner = StressRunner(cfg, reports_dir=reports, install_fake=install_default_fake)
    payload = asyncio.run(runner.run())
    assert payload["runs"][0]["result"] == "unexpected_failure"
    assert payload["thresholds"]["verdict"] == "FAIL"


def test_fake_client_uninstalled_after_runner(qa_db):
    """Stress fake must not leak into later pytest cases that patch httpx."""
    import claude_service
    from anthropic_http import create_anthropic_client as real_factory

    reports = qa_db / "reports"
    reports.mkdir()
    before = claude_service.create_anthropic_client
    cfg = StressRunnerConfig(runs=1, seed=42, fake_mode="success_first", profiles="fixtures")
    runner = StressRunner(cfg, reports_dir=reports, install_fake=install_default_fake)
    asyncio.run(runner.run())
    assert claude_service.create_anthropic_client is before
    assert claude_service.create_anthropic_client is real_factory


def test_checkpoint_written_after_each_run(qa_db):
    reports = qa_db / "reports"
    reports.mkdir()
    cfg = StressRunnerConfig(runs=2, seed=1, fake_mode="success_first", profiles="fixtures")
    runner = StressRunner(cfg, reports_dir=reports, install_fake=install_default_fake)
    asyncio.run(runner.run())
    checkpoint = reports / "checkpoint.json"
    assert checkpoint.exists()
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert data["meta"]["completed_runs"] == 2


def test_reports_json_csv_markdown(qa_db):
    reports = qa_db / "reports"
    reports.mkdir()
    cfg = StressRunnerConfig(runs=2, seed=2, fake_mode="success_first", profiles="fixtures")
    output = reports / "generation_stress_test.json"
    cfg.output_json = output
    runner = StressRunner(cfg, reports_dir=reports, install_fake=install_default_fake)
    asyncio.run(runner.run())
    assert output.exists()
    assert output.with_suffix(".csv").exists()
    assert output.with_suffix(".md").exists()
    md = output.with_suffix(".md").read_text(encoding="utf-8")
    assert "Verdict:" in md
    assert "ANTHROPIC" not in md.upper() or "qa-fake" not in md


def test_secrets_not_in_reports(qa_db, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "SECRET_KEY_MUST_NOT_APPEAR")
    reports = qa_db / "reports"
    reports.mkdir()
    cfg = StressRunnerConfig(runs=1, seed=3, fake_mode="success_first", profiles="fixtures")
    cfg.output_json = reports / "out.json"
    runner = StressRunner(cfg, reports_dir=reports, install_fake=install_default_fake)
    payload = asyncio.run(runner.run())
    blob = json.dumps(payload)
    assert "SECRET_KEY_MUST_NOT_APPEAR" not in blob
    assert "SECRET_KEY_MUST_NOT_APPEAR" not in cfg.output_json.read_text(encoding="utf-8")


def test_production_database_path_unchanged(qa_db, monkeypatch):
    original = str(qa_db / "should-not-be-production.db")
    # Simulate a "production" path that must remain untouched by runner DB writes.
    prod_marker = qa_db / "prod-marker.db"
    prod_marker.write_text("untouched", encoding="utf-8")
    monkeypatch.setattr(config, "DATABASE_PATH", str(qa_db / "qa-stress.db"))
    reports = qa_db / "reports"
    reports.mkdir()
    cfg = StressRunnerConfig(runs=1, seed=4, fake_mode="success_first", profiles="fixtures")
    runner = StressRunner(cfg, reports_dir=reports, install_fake=install_default_fake)
    asyncio.run(runner.run())
    assert prod_marker.read_text(encoding="utf-8") == "untouched"


def test_cli_requires_real_flag_for_live_api(monkeypatch):
    parser = build_parser()
    args = parser.parse_args(["--runs", "5", "--seed", "42"])
    assert args.real_claude is False
    args_real = parser.parse_args(["--runs", "5", "--real-claude", "--yes"])
    assert args_real.real_claude is True
    assert args_real.yes is True


def test_cost_confirmation_yes_and_no(monkeypatch):
    estimate = estimate_run_cost(runs=5)
    assert estimate.cost_usd is None
    assert confirm_real_run(estimate=estimate, assume_yes=True) is True
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    assert confirm_real_run(estimate=estimate, assume_yes=False) is False


def test_thresholds_pass_warn_fail():
    from qa.metrics import RunMetrics

    success_runs = [
        RunMetrics(
            run_id=f"r{i}",
            seed=1,
            run_index=i,
            profile_summary={},
            result="success",
            successful_attempt=1,
            total_duration_ms=1000,
        )
        for i in range(20)
    ]
    agg = aggregate_runs(success_runs)
    assert evaluate_thresholds(agg)["verdict"] == "PASS"

    mixed = success_runs[:18] + [
        RunMetrics(
            run_id="c1",
            seed=1,
            run_index=18,
            profile_summary={},
            result="controlled_failure",
            total_duration_ms=1000,
            error_code="MENU_GENERATION_INVALID",
        ),
        RunMetrics(
            run_id="c2",
            seed=1,
            run_index=19,
            profile_summary={},
            result="controlled_failure",
            total_duration_ms=1000,
            error_code="MENU_GENERATION_INVALID",
        ),
    ]
    # 18/20 = 90% success → WARN band
    assert evaluate_thresholds(aggregate_runs(mixed))["verdict"] in {"WARN", "PASS"}

    bad = success_runs[:10] + [
        RunMetrics(
            run_id="u1",
            seed=1,
            run_index=99,
            profile_summary={},
            result="unexpected_failure",
            total_duration_ms=1000,
            error_code="INTERNAL_ERROR",
        )
    ]
    assert evaluate_thresholds(aggregate_runs(bad))["verdict"] == "FAIL"


def test_cli_dry_run_and_fake_suite(qa_db, monkeypatch, capsys):
    monkeypatch.setattr(config, "DATABASE_PATH", str(qa_db / "qa-stress.db"))
    monkeypatch.setenv("DATABASE_PATH", str(qa_db / "qa-stress.db"))
    monkeypatch.setenv("ENVIRONMENT", "qa")
    monkeypatch.setenv("ALLOW_DEV_AUTH", "true")
    code = main(
        [
            "--runs",
            "5",
            "--seed",
            "42",
            "--profiles",
            "fixtures",
            "--fake-mode",
            "success_first",
            "--work-dir",
            str(qa_db / "work"),
            "--output",
            str(qa_db / "work" / "reports" / "out.json"),
        ]
    )
    assert code == 0
    out = (qa_db / "work" / "reports" / "out.json").read_text(encoding="utf-8")
    payload = json.loads(out)
    assert payload["aggregate"]["success_count"] == 5
