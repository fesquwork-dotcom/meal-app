"""CLI: python -m qa.generation_stress_test --runs 100

Isolated generation reliability stress runner (Sprint 10.4).
Does not change production generation behavior.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from qa.cost_estimate import confirm_real_run, estimate_run_cost
from qa.isolation import isolated_qa_environment
from qa.runner import StressRunner, StressRunnerConfig, install_default_fake


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Keep QA summary separate from noisy third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m qa.generation_stress_test",
        description="Generation reliability stress test (isolated QA runner)",
    )
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON report path (CSV/MD written alongside)",
    )
    parser.add_argument(
        "--profiles",
        choices=("generated", "fixtures", "mixed"),
        default="generated",
    )
    parser.add_argument(
        "--real-claude",
        action="store_true",
        help="Call the real Anthropic API (requires confirmation unless --yes)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay-seconds", type=float, default=0.0)
    parser.add_argument("--save-failed-payloads", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Skip real-API confirmation")
    parser.add_argument(
        "--fake-mode",
        default="success_first",
        choices=(
            "success_first",
            "success_after_retry",
            "always_constraint",
            "unexpected",
            "truncate",
        ),
        help="Offline fake Claude behavior (ignored with --real-claude)",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep temporary QA work directory after completion",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional fixed work directory (implies keep if provided)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    args = build_parser().parse_args(argv)

    if args.concurrency != 1:
        logging.getLogger("qa.stress").warning(
            "concurrency=%s requested; runner executes sequentially for analyzable results",
            args.concurrency,
        )

    if args.real_claude:
        estimate = estimate_run_cost(runs=args.runs)
        if not confirm_real_run(estimate=estimate, assume_yes=args.yes):
            print("Aborted.")
            return 2

    keep = bool(args.keep_artifacts or args.work_dir)
    with isolated_qa_environment(keep_artifacts=keep, work_dir=args.work_dir) as isolation:
        # Reload config after env overrides.
        import importlib

        import config as config_module

        importlib.reload(config_module)

        output = args.output
        if output is None:
            from datetime import datetime, timezone

            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output = isolation.reports_dir / f"generation_stress_{stamp}.json"

        cfg = StressRunnerConfig(
            runs=args.runs,
            seed=args.seed,
            concurrency=args.concurrency,
            profiles=args.profiles,
            real_claude=args.real_claude,
            dry_run=args.dry_run,
            delay_seconds=args.delay_seconds,
            save_failed_payloads=args.save_failed_payloads,
            output_json=output,
            yes=args.yes,
            fake_mode=args.fake_mode,
            keep_artifacts=keep,
        )
        runner = StressRunner(
            cfg,
            reports_dir=isolation.reports_dir,
            failed_payloads_dir=isolation.failed_payloads_dir
            if args.save_failed_payloads
            else None,
            install_fake=None if args.real_claude else install_default_fake,
        )
        payload = asyncio.run(runner.run())

        if args.dry_run:
            print(f"Dry run prepared {len(payload.get('profiles') or [])} profiles.")
            return 0

        verdict = (payload.get("thresholds") or {}).get("verdict", "FAIL")
        print(f"Verdict: {verdict}")
        print(f"JSON: {output}")
        print(f"CSV:  {output.with_suffix('.csv')}")
        print(f"MD:   {output.with_suffix('.md')}")
        if verdict == "FAIL":
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
