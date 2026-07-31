"""JSON / CSV / Markdown report writers for stress tests."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qa.metrics import RunMetrics
from qa.thresholds import evaluate_thresholds


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv_report(path: Path, runs: list[RunMetrics]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id",
        "run_index",
        "seed",
        "result",
        "successful_attempt",
        "total_duration_ms",
        "days",
        "persons",
        "meal_types",
        "budget",
        "budget_tier",
        "cooking_time_limit",
        "goal",
        "dietary_label",
        "request_id",
        "error_code",
        "error_type",
        "issue_count",
        "regression_detected",
        "unique_recipe_count",
        "meal_count",
        "basket_item_count",
        "canonical_total_cost",
        "model_total_cost",
        "total_cost_difference",
        "recipe_cost",
        "shopping_cost",
        "budget_usage_percent",
        "leftovers_count",
        "shared_cooking_instances",
        "parse_or_schema_failure",
        "max_tokens_failure",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for run in runs:
            writer.writerow(
                {
                    "run_id": run.run_id,
                    "run_index": run.run_index,
                    "seed": run.seed,
                    "result": run.result,
                    "successful_attempt": run.successful_attempt,
                    "total_duration_ms": run.total_duration_ms,
                    "days": run.days,
                    "persons": run.persons,
                    "meal_types": "+".join(run.meal_types),
                    "budget": run.budget,
                    "budget_tier": run.budget_tier,
                    "cooking_time_limit": run.cooking_time_limit,
                    "goal": run.goal,
                    "dietary_label": run.dietary_label,
                    "request_id": run.request_id,
                    "error_code": run.error_code,
                    "error_type": run.error_type,
                    "issue_count": run.issue_count,
                    "regression_detected": run.regression_detected,
                    "unique_recipe_count": run.unique_recipe_count,
                    "meal_count": run.meal_count,
                    "basket_item_count": run.basket_item_count,
                    "canonical_total_cost": run.canonical_total_cost,
                    "model_total_cost": run.model_total_cost,
                    "total_cost_difference": run.total_cost_difference,
                    "recipe_cost": run.recipe_cost,
                    "shopping_cost": run.shopping_cost,
                    "budget_usage_percent": run.budget_usage_percent,
                    "leftovers_count": run.leftovers_count,
                    "shared_cooking_instances": run.shared_cooking_instances,
                    "parse_or_schema_failure": run.parse_or_schema_failure,
                    "max_tokens_failure": run.max_tokens_failure,
                }
            )


def write_markdown_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    aggregate = payload.get("aggregate") or {}
    thresholds = payload.get("thresholds") or evaluate_thresholds(aggregate)
    meta = payload.get("meta") or {}
    runs: list[dict[str, Any]] = payload.get("runs") or []

    lines: list[str] = []
    lines.append("# Generation Reliability Stress Test")
    lines.append("")
    lines.append(f"- Generated at: `{_utc_now()}`")
    lines.append(f"- Environment: `{meta.get('environment', 'qa')}`")
    lines.append(f"- Claude model: `{meta.get('claude_model', 'unknown')}`")
    lines.append(f"- Commit SHA: `{meta.get('commit_sha', 'unknown')}`")
    lines.append(f"- Real Claude: `{meta.get('real_claude', False)}`")
    lines.append(f"- Runs: `{meta.get('runs')}` · seed `{meta.get('seed')}` · concurrency `{meta.get('concurrency')}`")
    lines.append(f"- Profiles: `{meta.get('profiles')}`")
    lines.append("")
    lines.append(f"## Verdict: **{thresholds.get('verdict')}**")
    lines.append("")
    for reason in thresholds.get("reasons") or []:
        lines.append(f"- {reason}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    for key in (
        "success_rate",
        "success_on_attempt_1",
        "success_on_attempt_2",
        "success_on_attempt_3",
        "success_by_attempt_2_rate",
        "controlled_failure_rate",
        "unexpected_failure_rate",
        "correction_regression_rate",
        "parse_schema_failure_rate",
        "max_tokens_failure_rate",
        "mean_attempts",
    ):
        lines.append(f"| {key} | {aggregate.get(key)} |")
    duration = aggregate.get("duration_ms") or {}
    lines.append(
        f"| duration_ms p50/p90/p95/max | "
        f"{duration.get('p50')} / {duration.get('p90')} / {duration.get('p95')} / {duration.get('max')} |"
    )
    tokens = aggregate.get("output_tokens") or {}
    lines.append(
        f"| output_tokens mean/p50/p90/max | "
        f"{tokens.get('mean')} / {tokens.get('p50')} / {tokens.get('p90')} / {tokens.get('max')} |"
    )
    usage = aggregate.get("budget_utilization") or {}
    lines.append(
        f"| budget_utilization mean/min/max/p50/p90 | "
        f"{usage.get('mean')} / {usage.get('min')} / {usage.get('max')} / "
        f"{usage.get('p50')} / {usage.get('p90')} |"
    )
    lines.append(f"| budget_utilization in_target_90_100_rate | {usage.get('in_target_90_100_rate')} |")
    lines.append("")

    lines.append("## Attempt distribution")
    lines.append("")
    dist = aggregate.get("attempt_distribution") or {}
    lines.append(f"- Attempt 1: {dist.get('1', 0)}")
    lines.append(f"- Attempt 2: {dist.get('2', 0)}")
    lines.append(f"- Attempt 3: {dist.get('3', 0)}")
    lines.append("")

    lines.append("## Top issue codes")
    lines.append("")
    freq = aggregate.get("issue_code_frequency") or {}
    if not freq:
        lines.append("- (none)")
    else:
        for code, count in list(freq.items())[:15]:
            lines.append(f"- `{code}`: {count}")
    lines.append("")

    slow = sorted(runs, key=lambda r: int(r.get("total_duration_ms") or 0), reverse=True)[:5]
    lines.append("## Slowest scenarios")
    lines.append("")
    for run in slow:
        summary = run.get("profile_summary") or {}
        lines.append(
            f"- run `{run.get('run_id')}` · {run.get('total_duration_ms')} ms · "
            f"days={summary.get('days')} persons={summary.get('persons')} "
            f"goal={summary.get('goal')} result={run.get('result')}"
        )
    lines.append("")

    token_heavy = sorted(
        runs,
        key=lambda r: max(
            (a.get("output_tokens") or 0 for a in (r.get("attempts") or [])),
            default=0,
        ),
        reverse=True,
    )[:5]
    lines.append("## Highest output-token scenarios")
    lines.append("")
    for run in token_heavy:
        peak = max((a.get("output_tokens") or 0 for a in (run.get("attempts") or [])), default=0)
        lines.append(f"- run `{run.get('run_id')}` · peak_output_tokens={peak} · result={run.get('result')}")
    lines.append("")

    controlled = [r for r in runs if r.get("result") == "controlled_failure"]
    unexpected = [r for r in runs if r.get("result") == "unexpected_failure"]
    lines.append("## Controlled failures")
    lines.append("")
    if not controlled:
        lines.append("- (none)")
    else:
        for run in controlled:
            lines.append(
                f"- `{run.get('run_id')}` · {run.get('error_code')} · {run.get('error_type')} · "
                f"issues={run.get('issue_codes_final')}"
            )
    lines.append("")
    lines.append("## Unexpected failures")
    lines.append("")
    if not unexpected:
        lines.append("- (none)")
    else:
        for run in unexpected:
            lines.append(
                f"- `{run.get('run_id')}` · {run.get('error_code')} · {run.get('error_type')} · "
                f"{run.get('error_message')}"
            )
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    verdict = thresholds.get("verdict")
    if verdict == "PASS":
        lines.append("- Pipeline meets initial reliability targets for this sample size.")
        lines.append("- Safe to scale toward 100 real runs if cost estimate is acceptable.")
    elif verdict == "WARN":
        lines.append("- Investigate top issue codes and correction regressions before large real runs.")
        lines.append("- Prefer targeted fixes over weakening validators.")
    else:
        lines.append("- Do not scale real API volume until unexpected failures and low success rate are fixed.")
        lines.append("- Re-run with fake client scenarios that reproduce the failing profiles.")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def build_report_payload(
    *,
    meta: dict[str, Any],
    runs: list[RunMetrics],
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    thresholds = evaluate_thresholds(aggregate)
    return {
        "meta": meta,
        "thresholds": thresholds,
        "aggregate": aggregate,
        "runs": [run.to_dict() for run in runs],
    }
