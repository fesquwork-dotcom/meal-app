"""Sprint 10.6 — async generation jobs API."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

import config
import database
import generation_jobs.execute as execute_mod
import main
from claude_exceptions import ClaudeTimeoutError, MenuConstraintError
from generation_jobs.errors import ERROR_CODE_INTERRUPTED
from generation_jobs.repository import GenerationJobRepository
from generation_jobs.worker import GenerationWorker
from main import app
from tests.menu_fixtures import build_valid_menu_dict
from tests.profile_test_helpers import (
    generate_with_token,
    issue_preview_token,
    save_profile,
)


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "generation-jobs.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "GENERATION_MAX_CONCURRENT_JOBS", 1)
    asyncio.run(database.init_db())


@pytest.fixture(autouse=True)
def _configure_auth(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


@pytest.fixture
def client(monkeypatch):
    # Ensure worker asyncio primitives bind to this TestClient loop.
    from generation_jobs import worker as worker_mod

    monkeypatch.setattr(worker_mod, "_worker", None)
    with TestClient(app) as test_client:
        yield test_client
    # Drop singleton after lifespan stop so the next test recreates cleanly.
    worker_mod.reset_generation_worker_for_tests()


def _create_job(client, token: str):
    return client.post("/api/generation-jobs", json={"preview_token": token})


def _wait_job(client, job_id: str, *, timeout_s: float = 8.0) -> dict:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/generation-jobs/{job_id}")
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in ("succeeded", "failed", "cancelled"):
            return last
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {last}")


def _blocking_generate(gate: threading.Event):
    async def slow_generate(**_kwargs):
        while not gate.is_set():
            await asyncio.sleep(0.05)
        return build_valid_menu_dict(days=3)

    return slow_generate


def test_create_returns_202_queued(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")
    gate = threading.Event()
    monkeypatch.setattr(execute_mod, "generate_menu", _blocking_generate(gate))

    try:
        response = _create_job(client, token)
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["status"] == "queued"
        assert body["job_id"]
    finally:
        gate.set()
    _wait_job(client, body["job_id"])


def test_duplicate_create_returns_same_job_id(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    gate = threading.Event()
    monkeypatch.setattr(execute_mod, "generate_menu", _blocking_generate(gate))

    try:
        first = _create_job(client, token)
        assert first.status_code == 202
        job_id = first.json()["job_id"]

        second = _create_job(client, token)
        assert second.status_code == 202
        assert second.json()["job_id"] == job_id
    finally:
        gate.set()
    _wait_job(client, job_id)


def test_job_runs_to_succeeded_with_menu_plan_id(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")

    async def fake_generate(**_kwargs):
        return build_valid_menu_dict(days=3)

    monkeypatch.setattr(execute_mod, "generate_menu", fake_generate)

    created = _create_job(client, token)
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    final = _wait_job(client, job_id)
    assert final["status"] == "succeeded"
    assert final["menu_plan_id"]
    assert final["strategy_id"]
    assert final["stage"] == "completed"


def test_failed_generation_marks_failed(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def failing_generate(**_kwargs):
        raise MenuConstraintError("constraints", issue_codes=["BUDGET_EXCEEDED"])

    monkeypatch.setattr(execute_mod, "generate_menu", failing_generate)

    created = _create_job(client, token)
    job_id = created.json()["job_id"]
    final = _wait_job(client, job_id)
    assert final["status"] == "failed"
    assert final["error_code"] == "MENU_GENERATION_INVALID"
    assert final["safe_message"]
    assert "BUDGET" not in (final["safe_message"] or "")


def test_timeout_maps_safe_message(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def timeout_generate(**_kwargs):
        raise ClaudeTimeoutError("timeout")

    monkeypatch.setattr(execute_mod, "generate_menu", timeout_generate)

    job_id = _create_job(client, token).json()["job_id"]
    final = _wait_job(client, job_id)
    assert final["status"] == "failed"
    assert final["error_code"] == "MENU_GENERATION_TIMEOUT"
    assert "слишком много времени" in final["safe_message"]


def test_other_user_gets_404(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    gate = threading.Event()
    monkeypatch.setattr(execute_mod, "generate_menu", _blocking_generate(gate))

    try:
        job_id = _create_job(client, token).json()["job_id"]

        monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)
        response = client.get(f"/api/generation-jobs/{job_id}")
        assert response.status_code == 404
        assert response.json()["code"] == "GENERATION_JOB_NOT_FOUND"
    finally:
        gate.set()


def test_active_endpoint(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    gate = threading.Event()
    monkeypatch.setattr(execute_mod, "generate_menu", _blocking_generate(gate))

    try:
        empty = client.get("/api/generation-jobs/active")
        assert empty.status_code == 200
        assert empty.json()["job"] is None

        job_id = _create_job(client, token).json()["job_id"]
        active = client.get("/api/generation-jobs/active")
        assert active.status_code == 200
        body = active.json()
        assert body["job"] is not None
        assert body["job"]["job_id"] == job_id
        assert body["job"]["status"] in ("queued", "running")
    finally:
        gate.set()
    _wait_job(client, job_id)
    after = client.get("/api/generation-jobs/active")
    assert after.json()["job"] is None


def test_interrupt_running_on_startup_marks_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "interrupt.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())

    repo = GenerationJobRepository()

    async def seed():
        await repo.create(
            job_id="job-running-1",
            user_id=1,
            request_json="{}",
            days=3,
            persons=2,
            plan_start_date="2026-07-13",
        )
        await repo.mark_running("job-running-1")

    asyncio.run(seed())
    worker = GenerationWorker(repository=repo)
    count = asyncio.run(worker.interrupt_running_on_startup())
    assert count == 1
    record = asyncio.run(repo.get("job-running-1"))
    assert record is not None
    assert record.status == "failed"
    assert record.error_code == ERROR_CODE_INTERRUPTED
    assert record.safe_message


def test_legacy_generate_menu_still_works(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def fake_generate(**_kwargs):
        return build_valid_menu_dict(days=3)

    monkeypatch.setattr(main, "generate_menu", fake_generate)

    response = generate_with_token(client, token)
    assert response.status_code == 200
    body = response.json()
    assert "days_plan" in body
    assert body.get("strategy_id")
    assert body.get("menu_plan_id")


def test_job_state_persists_in_sqlite(client, monkeypatch, tmp_path):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")

    async def fake_generate(**_kwargs):
        return build_valid_menu_dict(days=3)

    monkeypatch.setattr(execute_mod, "generate_menu", fake_generate)

    job_id = _create_job(client, token).json()["job_id"]
    final = _wait_job(client, job_id)
    assert final["status"] == "succeeded"

    repo = GenerationJobRepository()
    record = asyncio.run(repo.get(job_id))
    assert record is not None
    assert record.status == "succeeded"
    assert record.menu_plan_id == final["menu_plan_id"]
    assert record.request_json in ("", None)


def test_status_does_not_leak_provider_secrets(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def boom(**_kwargs):
        raise ClaudeTimeoutError(
            "Anthropic sk-ant-secret-key-xyz stacktrace traceback"
        )

    monkeypatch.setattr(execute_mod, "generate_menu", boom)

    job_id = _create_job(client, token).json()["job_id"]
    final = _wait_job(client, job_id)
    blob = str(final)
    assert "sk-ant" not in blob
    assert "stacktrace" not in blob.lower()
    assert "traceback" not in blob.lower()
    assert final["safe_message"]
    assert "Anthropic" not in (final["safe_message"] or "")


def test_status_exposes_stages_while_running(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    gate = threading.Event()
    monkeypatch.setattr(execute_mod, "generate_menu", _blocking_generate(gate))

    try:
        job_id = _create_job(client, token).json()["job_id"]
        seen_stages: set[str] = set()
        deadline = time.time() + 5.0
        while time.time() < deadline:
            body = client.get(f"/api/generation-jobs/{job_id}").json()
            seen_stages.add(body["stage"])
            if body["status"] == "running" and body["stage"] in (
                "preparing",
                "generating",
            ):
                break
            time.sleep(0.05)
    finally:
        gate.set()
    final = _wait_job(client, job_id)
    assert final["stage"] == "completed"
    assert seen_stages & {"queued", "preparing", "generating", "saving", "completed"}


def test_concurrency_bound_keeps_second_job_queued(client, monkeypatch):
    """With max_concurrent=1, a second user's job stays queued until the first finishes."""
    gate = threading.Event()
    monkeypatch.setattr(execute_mod, "generate_menu", _blocking_generate(gate))

    try:
        save_profile(client, expected_revision=0)
        token_a = issue_preview_token(client)
        job_a = _create_job(client, token_a).json()["job_id"]

        # Wait until A is running (holds the semaphore).
        deadline = time.time() + 5.0
        while time.time() < deadline:
            status_a = client.get(f"/api/generation-jobs/{job_a}").json()
            if status_a["status"] == "running":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("job A never started")

        monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)
        save_profile(client, expected_revision=0)
        token_b = issue_preview_token(client)
        job_b = _create_job(client, token_b).json()["job_id"]

        # While A is blocked, B must remain queued (not running).
        time.sleep(0.2)
        status_b = client.get(f"/api/generation-jobs/{job_b}").json()
        assert status_b["status"] == "queued"
        assert status_b["stage"] == "queued"
    finally:
        gate.set()

    final_b = _wait_job(client, job_b)
    assert final_b["status"] == "succeeded"

    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    final_a = _wait_job(client, job_a)
    assert final_a["status"] == "succeeded"


def test_atomic_claim_prevents_double_execution(tmp_path, monkeypatch):
    db_path = tmp_path / "claim.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    repo = GenerationJobRepository()

    async def seed_and_claim():
        await repo.create(
            job_id="job-claim-1",
            user_id=1,
            request_json='{"ok":true}',
            days=3,
            persons=1,
            plan_start_date="2026-07-13",
        )
        first = await repo.mark_running("job-claim-1", clear_request_json=True)
        second = await repo.mark_running("job-claim-1", clear_request_json=True)
        return first, second

    first, second = asyncio.run(seed_and_claim())
    assert first is not None
    assert first.status == "running"
    assert second is None
