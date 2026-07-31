"""Isolated temporary database / environment for stress runs."""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger("qa.stress")


@dataclass
class IsolationContext:
    """Active isolation resources for one stress-test session."""

    work_dir: Path
    database_path: Path
    reports_dir: Path
    failed_payloads_dir: Path
    previous_env: dict[str, str | None]
    keep_artifacts: bool = False


def _snapshot_env(keys: list[str]) -> dict[str, str | None]:
    return {key: os.environ.get(key) for key in keys}


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@contextmanager
def isolated_qa_environment(
    *,
    keep_artifacts: bool = False,
    work_dir: Path | None = None,
) -> Iterator[IsolationContext]:
    """Point config at a temporary SQLite DB and QA environment variables.

    Restores previous env on exit. Deletes the work directory unless keep_artifacts.
    """
    env_keys = [
        "DATABASE_PATH",
        "ENVIRONMENT",
        "ALLOW_DEV_AUTH",
        "DEV_TELEGRAM_USER_ID",
    ]
    previous = _snapshot_env(env_keys)

    root = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="meal-qa-stress-"))
    root.mkdir(parents=True, exist_ok=True)
    db_path = root / "qa_stress.db"
    reports_dir = root / "reports"
    failed_dir = root / "failed_payloads"
    reports_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    os.environ["DATABASE_PATH"] = str(db_path)
    os.environ["ENVIRONMENT"] = "qa"
    os.environ["ALLOW_DEV_AUTH"] = "true"
    os.environ["DEV_TELEGRAM_USER_ID"] = "910001"

    ctx = IsolationContext(
        work_dir=root,
        database_path=db_path,
        reports_dir=reports_dir,
        failed_payloads_dir=failed_dir,
        previous_env=previous,
        keep_artifacts=keep_artifacts,
    )

    def _cleanup() -> None:
        _restore_env(previous)
        if not keep_artifacts and root.exists() and work_dir is None:
            shutil.rmtree(root, ignore_errors=True)

    atexit.register(_cleanup)
    logger.info(
        "stress_isolation_ready work_dir=%s database_path=%s",
        root,
        db_path,
    )
    try:
        yield ctx
    finally:
        atexit.unregister(_cleanup)
        _restore_env(previous)
        if not keep_artifacts and work_dir is None and root.exists():
            shutil.rmtree(root, ignore_errors=True)
            logger.info("stress_isolation_cleaned work_dir=%s", root)
