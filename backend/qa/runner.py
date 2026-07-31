"""Stress-test runner: isolated generate_menu loops with checkpointing."""

from __future__ import annotations

import asyncio
import logging
import re
import signal
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import config
import database
from claude_exceptions import (
    ClaudeJsonError,
    ClaudeOutputTruncatedError,
    ClaudeTimeoutError,
    ClaudeUnavailableError,
    ClaudeValidationError,
    MenuConstraintError,
)
from qa.capture import LogCapture
from qa.fake_claude import FakeClaudeController, build_fake_client
from qa.metrics import (
    AttemptMetrics,
    RunMetrics,
    aggregate_runs,
    classify_exception,
)
from qa.profiles import StressProfile, generate_profiles
from qa.reports import build_report_payload, write_csv_report, write_json_report, write_markdown_report
from strategy.builder import StrategyBuilder
from strategy.planner_input import build_planner_input

logger = logging.getLogger("qa.stress")

_INTERRUPTED = False


def _handle_interrupt(_signum, _frame) -> None:
    global _INTERRUPTED
    _INTERRUPTED = True
    logger.warning("stress_test_interrupted signal_received=true")


def _git_sha() -> str:
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:40]
    except Exception:
        pass
    return "unknown"


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() in {"true", "1", "yes"}


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _enrich_from_logs(run: RunMetrics, messages: list[str]) -> None:
    attempts: dict[int, AttemptMetrics] = {}

    for message in messages:
        if "claude_response_received" in message:
            attempt = _parse_int(_kv(message, "attempt")) or 1
            metrics = attempts.setdefault(attempt, AttemptMetrics(attempt=attempt))
            metrics.output_tokens = _parse_int(_kv(message, "output_tokens"))
            metrics.stop_reason = _kv(message, "stop_reason")
            metrics.raw_chars = _parse_int(_kv(message, "raw_chars"))
        if "generation_retry" in message and "retry_mode=" in message:
            attempt = _parse_int(_kv(message, "attempt")) or 1
            metrics = attempts.setdefault(attempt, AttemptMetrics(attempt=attempt))
            metrics.retry_mode = _kv(message, "retry_mode")
            metrics.strict = _parse_bool(_kv(message, "strict"))
            metrics.continue_from_best = _parse_bool(_kv(message, "continue_from_best"))
        if "correction_regression_detected" in message:
            run.regression_detected = True
            reasons = _kv(message, "reasons")
            if reasons:
                run.regression_reasons.append(reasons)
        if "total_cost_normalized" in message:
            run.model_total_cost = _parse_float(_kv(message, "model_total"))
            run.canonical_total_cost = _parse_float(_kv(message, "calculated_total"))
            run.total_cost_difference = _parse_float(_kv(message, "difference"))
        if "generation_started" in message:
            run.request_id = _kv(message, "request_id") or run.request_id
            run.strategy_version = _kv(message, "strategy_version") or run.strategy_version
        if "event=output_truncated" in message or "retry_mode=compact_output" in message:
            run.max_tokens_failure = True
        if "event=json_parse" in message or "event=schema_validation" in message:
            run.parse_or_schema_failure = True
        if "event=timeout" in message:
            run.api_timeout = True
        if "status=429" in message:
            run.api_rate_limited = True
        if re.search(r"status=5\d\d", message):
            run.api_5xx = True

    run.attempts = [attempts[key] for key in sorted(attempts)]


def _kv(message: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}=([^\s]+)", message)
    return match.group(1) if match else None


def _menu_stats_from_result(result: dict[str, object], run: RunMetrics) -> None:
    recipes = result.get("recipes")
    days_plan = result.get("days_plan")
    basket = result.get("basket")
    if isinstance(recipes, list):
        ids = {
            (r.get("recipe_id") if isinstance(r, dict) else None)
            or (r.get("name") if isinstance(r, dict) else None)
            for r in recipes
        }
        run.unique_recipe_count = len({x for x in ids if x})
    if isinstance(days_plan, list):
        meal_count = 0
        leftovers = 0
        instance_counts: dict[str, int] = {}
        for day in days_plan:
            if not isinstance(day, dict):
                continue
            meals = day.get("meals")
            if not isinstance(meals, list):
                continue
            for meal in meals:
                if not isinstance(meal, dict):
                    continue
                meal_count += 1
                if meal.get("uses_leftovers"):
                    leftovers += 1
                instance = meal.get("cooking_instance_id")
                if isinstance(instance, str) and instance:
                    instance_counts[instance] = instance_counts.get(instance, 0) + 1
        run.meal_count = meal_count
        run.leftovers_count = leftovers
        run.shared_cooking_instances = sum(1 for count in instance_counts.values() if count > 1)
    if isinstance(basket, list):
        count = 0
        for category in basket:
            if isinstance(category, dict) and isinstance(category.get("items"), list):
                count += len(category["items"])
        run.basket_item_count = count
    total = result.get("total_cost")
    if isinstance(total, (int, float)):
        run.canonical_total_cost = float(total)
    shopping = result.get("shopping_cost", total)
    if isinstance(shopping, (int, float)):
        run.shopping_cost = float(shopping)
    recipe = result.get("recipe_cost")
    if isinstance(recipe, (int, float)):
        run.recipe_cost = float(recipe)
    usage = result.get("budget_usage_percent")
    if isinstance(usage, (int, float)):
        run.budget_usage_percent = float(usage)
    elif (
        isinstance(shopping, (int, float))
        and run.budget
        and run.budget > 0
    ):
        run.budget_usage_percent = round(100.0 * float(shopping) / float(run.budget), 1)


@dataclass
class StressRunnerConfig:
    runs: int = 100
    seed: int = 42
    concurrency: int = 1
    profiles: str = "generated"
    real_claude: bool = False
    dry_run: bool = False
    delay_seconds: float = 0.0
    save_failed_payloads: bool = False
    output_json: Path | None = None
    yes: bool = False
    fake_mode: str = "success_first"
    keep_artifacts: bool = False
    plan_start_date: date = field(default_factory=lambda: date(2026, 7, 18))


class StressRunner:
    def __init__(
        self,
        cfg: StressRunnerConfig,
        *,
        reports_dir: Path,
        failed_payloads_dir: Path | None = None,
        install_fake: Callable[[FakeClaudeController], Callable[[], None] | None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.reports_dir = reports_dir
        self.failed_payloads_dir = failed_payloads_dir
        self.install_fake = install_fake
        self.completed: list[RunMetrics] = []
        self.controller = FakeClaudeController(mode=cfg.fake_mode)

    async def run(self) -> dict[str, Any]:
        global _INTERRUPTED
        _INTERRUPTED = False
        previous_handler = signal.getsignal(signal.SIGINT)
        try:
            signal.signal(signal.SIGINT, _handle_interrupt)
        except Exception:
            previous_handler = None

        profiles = generate_profiles(
            runs=self.cfg.runs,
            seed=self.cfg.seed,
            mode=self.cfg.profiles,  # type: ignore[arg-type]
        )
        logger.info(
            "stress_test_started runs=%s seed=%s real_claude=%s profiles=%s concurrency=%s",
            self.cfg.runs,
            self.cfg.seed,
            self.cfg.real_claude,
            self.cfg.profiles,
            self.cfg.concurrency,
        )

        await database.init_db()

        uninstall_fake: Callable[[], None] | None = None
        try:
            if not self.cfg.real_claude and self.install_fake is not None:
                maybe_uninstall = self.install_fake(self.controller)
                if callable(maybe_uninstall):
                    uninstall_fake = maybe_uninstall

            if self.cfg.dry_run:
                logger.info("stress_test_dry_run profiles=%s", len(profiles))
                for profile in profiles:
                    logger.info("dry_run_profile %s", profile.summary())
                return {"dry_run": True, "profiles": [p.summary() for p in profiles]}

            # concurrency=1 recommended; keep sequential for analyzable results.
            for profile in profiles:
                if _INTERRUPTED:
                    break
                metrics = await self._run_one(profile)
                self.completed.append(metrics)
                self._checkpoint()
                if self.cfg.delay_seconds > 0 and not self.cfg.real_claude:
                    await asyncio.sleep(self.cfg.delay_seconds)
                elif self.cfg.delay_seconds > 0:
                    await asyncio.sleep(self.cfg.delay_seconds)

            aggregate = aggregate_runs(self.completed)
            meta = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "environment": config.ENVIRONMENT,
                "claude_model": config.CLAUDE_MODEL,
                "commit_sha": _git_sha(),
                "runs": self.cfg.runs,
                "completed_runs": len(self.completed),
                "seed": self.cfg.seed,
                "concurrency": self.cfg.concurrency,
                "profiles": self.cfg.profiles,
                "real_claude": self.cfg.real_claude,
                "interrupted": _INTERRUPTED,
                "fake_mode": None if self.cfg.real_claude else self.cfg.fake_mode,
            }
            payload = build_report_payload(meta=meta, runs=self.completed, aggregate=aggregate)
            paths = self._write_reports(payload)
            logger.info(
                "stress_test_completed completed_runs=%s verdict=%s json=%s",
                len(self.completed),
                payload["thresholds"]["verdict"],
                paths["json"],
            )
            return payload
        finally:
            if uninstall_fake is not None:
                uninstall_fake()
            if previous_handler is not None:
                try:
                    signal.signal(signal.SIGINT, previous_handler)
                except Exception:
                    pass

    async def _run_one(self, profile: StressProfile) -> RunMetrics:
        run_id = f"run_{profile.run_index:04d}_{uuid.uuid4().hex[:8]}"
        logger.info(
            "stress_run_started run_id=%s run_index=%s days=%s persons=%s",
            run_id,
            profile.run_index,
            profile.profile.get("days"),
            profile.persons,
        )
        started = time.monotonic()
        run = RunMetrics(
            run_id=run_id,
            seed=profile.seed,
            run_index=profile.run_index,
            profile_summary=profile.summary(),
            days=int(profile.profile.get("days") or 0),
            persons=profile.persons,
            meal_types=list(profile.profile.get("meal_types") or []),
            budget=float(profile.profile.get("budget") or 0),
            budget_tier=profile.budget_tier,
            cooktime=str(profile.profile.get("cooktime") or ""),
            dietary_label=profile.dietary_label,
            goal=str(profile.profile.get("goal") or ""),
        )

        try:
            strategy = StrategyBuilder().build(profile.profile)
            run.cooking_time_limit = strategy.cooking_time_limit
            run.strategy_version = strategy.strategy_version
            planner = build_planner_input(
                strategy=strategy,
                persons=profile.persons,
                proteins=list(profile.profile.get("proteins") or ["any"]),
                cooktime=str(profile.profile.get("cooktime") or "medium"),
                allergies=str(profile.profile.get("allergies") or "нет"),
                store=str(profile.profile.get("store") or "any"),
            )
            self.controller.strategy = strategy
            self.controller.call_count = 0
            self.controller.prompts.clear()

            if not self.cfg.real_claude and self.controller.mode == "unexpected":
                # Bypass generate_menu wrappers so the failure stays unexpected.
                raise RuntimeError("injected unexpected stress-test failure")

            import claude_service

            with LogCapture(["claude_service", "qa.stress"]) as events:
                try:
                    result = await claude_service.generate_menu(
                        **planner.as_generate_menu_kwargs(),
                        user_id=910001 + profile.run_index,
                        plan_start_date=self.cfg.plan_start_date,
                    )
                except Exception:
                    _enrich_from_logs(run, events.raw_messages)
                    raise
            _enrich_from_logs(run, events.raw_messages)
            if isinstance(result, dict):
                _menu_stats_from_result(result, run)
            run.result = "success"
            # Infer successful attempt from last Claude call count / log attempts.
            if run.attempts:
                run.successful_attempt = max(a.attempt for a in run.attempts)
            else:
                run.successful_attempt = 1
            logger.info(
                "stress_run_completed run_id=%s result=success attempt=%s duration_ms=%s",
                run_id,
                run.successful_attempt,
                int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:
            kind, code = classify_exception(exc)
            run.result = kind
            run.error_code = code
            run.error_type = type(exc).__name__
            run.error_message = str(exc)[:300]
            if isinstance(exc, MenuConstraintError):
                run.issue_codes_final = list(exc.issue_codes)
                run.issue_count = len(exc.issue_codes)
                stats = exc.menu_stats or {}
                if isinstance(stats.get("unique_recipe_count"), int):
                    run.unique_recipe_count = stats["unique_recipe_count"]
                if isinstance(stats.get("meal_count"), int):
                    run.meal_count = stats["meal_count"]
            if isinstance(exc, ClaudeOutputTruncatedError):
                run.max_tokens_failure = True
            if isinstance(exc, (ClaudeJsonError, ClaudeValidationError)):
                run.parse_or_schema_failure = True
            if isinstance(exc, ClaudeTimeoutError):
                run.api_timeout = True
            if isinstance(exc, ClaudeUnavailableError):
                run.api_5xx = True
            # Pull any logs captured before the exception if LogCapture was active.
            logger.warning(
                "stress_run_failed run_id=%s result=%s error_type=%s error_code=%s",
                run_id,
                kind,
                run.error_type,
                code,
            )
            if self.cfg.save_failed_payloads and self.failed_payloads_dir is not None:
                self._save_failed_payload(run, exc)

        run.total_duration_ms = int((time.monotonic() - started) * 1000)
        return run

    def _checkpoint(self) -> None:
        aggregate = aggregate_runs(self.completed)
        meta = {
            "checkpoint": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "completed_runs": len(self.completed),
            "seed": self.cfg.seed,
            "real_claude": self.cfg.real_claude,
        }
        payload = build_report_payload(meta=meta, runs=self.completed, aggregate=aggregate)
        path = self.reports_dir / "checkpoint.json"
        write_json_report(path, payload)
        logger.info(
            "stress_checkpoint_saved path=%s completed_runs=%s",
            path,
            len(self.completed),
        )

    def _write_reports(self, payload: dict[str, Any]) -> dict[str, str]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = self.cfg.output_json or (self.reports_dir / f"generation_stress_{stamp}.json")
        csv_path = json_path.with_suffix(".csv")
        md_path = json_path.with_suffix(".md")
        write_json_report(json_path, payload)
        write_csv_report(csv_path, self.completed)
        write_markdown_report(md_path, payload)
        return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}

    def _save_failed_payload(self, run: RunMetrics, exc: BaseException) -> None:
        assert self.failed_payloads_dir is not None
        path = self.failed_payloads_dir / f"{run.run_id}.txt"
        # Never write secrets — only sanitized exception + profile summary.
        body = (
            f"run_id={run.run_id}\n"
            f"error_type={type(exc).__name__}\n"
            f"error_code={run.error_code}\n"
            f"message={str(exc)[:500]}\n"
            f"profile={run.profile_summary}\n"
        )
        for secret_key in ("ANTHROPIC", "API_KEY", "TELEGRAM", "Bearer", "initData"):
            if secret_key.lower() in body.lower():
                body = "redacted: potential secret marker detected\n"
                break
        path.write_text(body, encoding="utf-8")


def install_default_fake(controller: FakeClaudeController) -> Callable[[], None]:
    """Patch Claude HTTP client for offline runs. Returns an uninstall callback."""
    import claude_service

    previous_create = claude_service.create_anthropic_client
    previous_sleep = claude_service.asyncio.sleep
    previous_api_key = config.ANTHROPIC_API_KEY
    api_key_injected = False

    async def _no_sleep(_seconds: float) -> None:
        return None

    claude_service.create_anthropic_client = build_fake_client(controller)  # type: ignore[assignment]
    claude_service.asyncio.sleep = _no_sleep  # type: ignore[assignment]
    if not config.ANTHROPIC_API_KEY:
        # generate_menu still builds headers; any non-empty value is fine offline.
        config.ANTHROPIC_API_KEY = "qa-fake-key-not-a-secret"
        api_key_injected = True

    def uninstall() -> None:
        claude_service.create_anthropic_client = previous_create
        claude_service.asyncio.sleep = previous_sleep
        if api_key_injected:
            config.ANTHROPIC_API_KEY = previous_api_key

    return uninstall
