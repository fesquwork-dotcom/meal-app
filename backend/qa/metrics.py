"""Metric models, result classification, and aggregation."""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ResultKind = Literal["success", "controlled_failure", "unexpected_failure"]

CONTROLLED_ERROR_CODES = frozenset(
    {
        "MENU_GENERATION_INVALID",
        "MENU_GENERATION_OUTPUT_TRUNCATED",
        "MENU_GENERATION_TIMEOUT",
        "MENU_GENERATION_UNAVAILABLE",
    }
)

CONTROLLED_EXCEPTION_NAMES = frozenset(
    {
        "MenuConstraintError",
        "ClaudeOutputTruncatedError",
        "ClaudeTimeoutError",
        "ClaudeUnavailableError",
        "ClaudeJsonError",
        "ClaudeValidationError",
    }
)


@dataclass
class AttemptMetrics:
    attempt: int
    duration_ms: int | None = None
    output_tokens: int | None = None
    stop_reason: str | None = None
    raw_chars: int | None = None
    issue_codes: list[str] = field(default_factory=list)
    retry_mode: str | None = None
    strict: bool | None = None
    continue_from_best: bool | None = None


@dataclass
class RunMetrics:
    run_id: str
    seed: int
    run_index: int
    profile_summary: dict[str, object]
    days: int | None = None
    persons: int | None = None
    meal_types: list[str] = field(default_factory=list)
    budget: float | None = None
    budget_tier: str | None = None
    cooking_time_limit: int | None = None
    cooktime: str | None = None
    dietary_label: str | None = None
    goal: str | None = None
    strategy_version: str | None = None
    request_id: str | None = None
    result: ResultKind = "unexpected_failure"
    successful_attempt: int | None = None
    total_duration_ms: int = 0
    attempts: list[AttemptMetrics] = field(default_factory=list)
    issue_codes_final: list[str] = field(default_factory=list)
    issue_count: int = 0
    regression_detected: bool = False
    regression_reasons: list[str] = field(default_factory=list)
    unique_recipe_count: int | None = None
    meal_count: int | None = None
    basket_item_count: int | None = None
    canonical_total_cost: float | None = None
    model_total_cost: float | None = None
    total_cost_difference: float | None = None
    recipe_cost: float | None = None
    shopping_cost: float | None = None
    budget_usage_percent: float | None = None
    leftovers_count: int | None = None
    shared_cooking_instances: int | None = None
    error_code: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    parse_or_schema_failure: bool = False
    max_tokens_failure: bool = False
    api_timeout: bool = False
    api_rate_limited: bool = False
    api_5xx: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def classify_exception(exc: BaseException) -> tuple[ResultKind, str | None]:
    """Map an exception to SUCCESS categories (never SUCCESS) and optional error code."""
    name = type(exc).__name__
    if name == "ClaudeOutputTruncatedError":
        return "controlled_failure", "MENU_GENERATION_OUTPUT_TRUNCATED"
    if name == "ClaudeTimeoutError":
        return "controlled_failure", "MENU_GENERATION_TIMEOUT"
    if name == "ClaudeUnavailableError":
        return "controlled_failure", "MENU_GENERATION_UNAVAILABLE"
    if name in {"MenuConstraintError", "ClaudeJsonError", "ClaudeValidationError"}:
        return "controlled_failure", "MENU_GENERATION_INVALID"
    if name in CONTROLLED_EXCEPTION_NAMES:
        return "controlled_failure", "MENU_GENERATION_INVALID"
    return "unexpected_failure", "INTERNAL_ERROR"


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def _duration_stats(values: list[int]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p50": None, "p90": None, "p95": None, "max": None}
    floats = sorted(float(v) for v in values)
    return {
        "mean": statistics.fmean(floats),
        "p50": _percentile(floats, 50),
        "p90": _percentile(floats, 90),
        "p95": _percentile(floats, 95),
        "max": floats[-1],
    }


def aggregate_runs(runs: list[RunMetrics]) -> dict[str, Any]:
    """Compute suite-level metrics from completed run records."""
    total = len(runs)
    if total == 0:
        return {"total_runs": 0}

    by_result = Counter(run.result for run in runs)
    success = [run for run in runs if run.result == "success"]
    attempt_dist = Counter(
        run.successful_attempt for run in success if run.successful_attempt is not None
    )

    issue_counter: Counter[str] = Counter()
    for run in runs:
        issue_counter.update(run.issue_codes_final)
        for attempt in run.attempts:
            issue_counter.update(attempt.issue_codes)

    output_tokens: list[int] = []
    for run in runs:
        for attempt in run.attempts:
            if attempt.output_tokens is not None:
                output_tokens.append(attempt.output_tokens)

    durations = [run.total_duration_ms for run in runs]
    attempt_counts = [
        len(run.attempts) if run.attempts else (1 if run.result == "success" else 0)
        for run in runs
    ]
    unique_counts = [run.unique_recipe_count for run in success if run.unique_recipe_count is not None]
    cost_diffs = [
        abs(run.total_cost_difference)
        for run in runs
        if run.total_cost_difference is not None
    ]
    canonical_costs = [
        run.canonical_total_cost
        for run in success
        if run.canonical_total_cost is not None
    ]
    usage_values = sorted(
        float(run.budget_usage_percent)
        for run in success
        if run.budget_usage_percent is not None
    )

    def rate(count: int) -> float:
        return round(100.0 * count / total, 2)

    success_n = by_result.get("success", 0)
    controlled_n = by_result.get("controlled_failure", 0)
    unexpected_n = by_result.get("unexpected_failure", 0)
    regression_n = sum(1 for run in runs if run.regression_detected)
    continue_best_n = sum(
        1
        for run in runs
        for attempt in run.attempts
        if attempt.continue_from_best
    )
    leftovers_n = sum(1 for run in success if (run.leftovers_count or 0) > 0)
    shared_n = sum(1 for run in success if (run.shared_cooking_instances or 0) > 0)
    parse_n = sum(1 for run in runs if run.parse_or_schema_failure)
    max_tokens_n = sum(1 for run in runs if run.max_tokens_failure)
    timeout_n = sum(1 for run in runs if run.api_timeout)
    rate_limit_n = sum(1 for run in runs if run.api_rate_limited)
    five_xx_n = sum(1 for run in runs if run.api_5xx)

    success_by_attempt_2 = sum(
        1 for run in success if run.successful_attempt is not None and run.successful_attempt <= 2
    )

    token_floats = sorted(float(v) for v in output_tokens)

    return {
        "total_runs": total,
        "success_rate": rate(success_n),
        "controlled_failure_rate": rate(controlled_n),
        "unexpected_failure_rate": rate(unexpected_n),
        "success_count": success_n,
        "controlled_failure_count": controlled_n,
        "unexpected_failure_count": unexpected_n,
        "success_on_attempt_1": rate(attempt_dist.get(1, 0)),
        "success_on_attempt_2": rate(attempt_dist.get(2, 0)),
        "success_on_attempt_3": rate(attempt_dist.get(3, 0)),
        "success_by_attempt_2_rate": rate(success_by_attempt_2),
        "attempt_distribution": {
            "1": attempt_dist.get(1, 0),
            "2": attempt_dist.get(2, 0),
            "3": attempt_dist.get(3, 0),
        },
        "mean_attempts": round(statistics.fmean(attempt_counts), 3) if attempt_counts else None,
        "duration_ms": _duration_stats(durations),
        "output_tokens": {
            "mean": statistics.fmean(token_floats) if token_floats else None,
            "p50": _percentile(token_floats, 50),
            "p90": _percentile(token_floats, 90),
            "max": token_floats[-1] if token_floats else None,
            "samples": len(token_floats),
        },
        "issue_code_frequency": dict(issue_counter.most_common()),
        "correction_regression_rate": rate(regression_n),
        "continue_from_best_runs": continue_best_n,
        "unique_recipe_count": {
            "mean": statistics.fmean(unique_counts) if unique_counts else None,
            "min": min(unique_counts) if unique_counts else None,
        },
        "canonical_total_cost": {
            "mean": statistics.fmean(canonical_costs) if canonical_costs else None,
        },
        "model_total_abs_error": {
            "mean": statistics.fmean(cost_diffs) if cost_diffs else None,
        },
        "budget_utilization": {
            "mean": statistics.fmean(usage_values) if usage_values else None,
            "min": usage_values[0] if usage_values else None,
            "max": usage_values[-1] if usage_values else None,
            "p50": _percentile(usage_values, 50),
            "p90": _percentile(usage_values, 90),
            "samples": len(usage_values),
            "in_target_90_100_rate": (
                round(
                    100.0
                    * sum(1 for value in usage_values if 90.0 <= value <= 100.0)
                    / len(usage_values),
                    2,
                )
                if usage_values
                else None
            ),
        },
        "leftovers_plan_rate": rate(leftovers_n) if success_n else 0.0,
        "shared_cooking_instance_rate": rate(shared_n) if success_n else 0.0,
        "parse_schema_failure_rate": rate(parse_n),
        "max_tokens_failure_rate": rate(max_tokens_n),
        "api_timeout_rate": rate(timeout_n),
        "api_429_rate": rate(rate_limit_n),
        "api_5xx_rate": rate(five_xx_n),
        "group_breakdown": _group_breakdown(runs),
    }


def _group_key_stats(runs: list[RunMetrics], key_fn) -> dict[str, dict[str, object]]:
    buckets: dict[str, list[RunMetrics]] = {}
    for run in runs:
        key = str(key_fn(run))
        buckets.setdefault(key, []).append(run)
    out: dict[str, dict[str, object]] = {}
    for key, group in sorted(buckets.items()):
        n = len(group)
        success_n = sum(1 for run in group if run.result == "success")
        out[key] = {
            "runs": n,
            "success_rate": round(100.0 * success_n / n, 2) if n else 0.0,
            "mean_duration_ms": round(
                statistics.fmean(run.total_duration_ms for run in group), 1
            ),
        }
    return out


def _group_breakdown(runs: list[RunMetrics]) -> dict[str, dict[str, dict[str, object]]]:
    return {
        "days": _group_key_stats(runs, lambda r: r.days),
        "persons": _group_key_stats(runs, lambda r: r.persons),
        "meal_types": _group_key_stats(
            runs, lambda r: "+".join(r.meal_types) if r.meal_types else "none"
        ),
        "cooking_time_limit": _group_key_stats(runs, lambda r: r.cooking_time_limit),
        "budget_tier": _group_key_stats(runs, lambda r: r.budget_tier or "unknown"),
        "dietary_label": _group_key_stats(runs, lambda r: r.dietary_label or "unknown"),
        "goal": _group_key_stats(runs, lambda r: r.goal or "unknown"),
    }
