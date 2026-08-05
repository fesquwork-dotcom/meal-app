"""Regression guards for backend Docker packaging (Sprint 10.6 hotfix).

Production failed with ModuleNotFoundError: generation_jobs because the
Dockerfile used an explicit package COPY whitelist. These tests ensure:

1. The image build copies the full runtime tree (not a fragile whitelist).
2. Required runtime packages are present on disk and not dockerignored.
3. Secrets / tests / local DBs stay out of the image context.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DOCKERFILE = BACKEND_ROOT / "Dockerfile"
DOCKERIGNORE = BACKEND_ROOT / ".dockerignore"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# Runtime packages imported by main.py (and siblings). New packages under
# backend/ should appear here when they become production imports.
REQUIRED_RUNTIME_PACKAGES = (
    "generation_jobs",
    "strategy",
    "shopping",
    "memory",
    "behavior",
    "decision",
    "learning",
    "learned_preferences",
    "insights",
    "trends",
    "menu_plan",
    "plan_delta",
    "dev_tools",
    "recipes",
    "recipe_catalog",
    "menu_generation",
)

MUST_EXCLUDE_PATTERNS = (
    ".env",
    ".venv/",
    "__pycache__/",
    "tests/",
    "qa/",
    "*.db",
)


def _dockerignore_lines() -> list[str]:
    return [
        line.strip()
        for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _path_ignored(rel_posix: str, patterns: list[str]) -> bool:
    """Approximate Docker .dockerignore matching for packaging guards."""
    path = PurePosixPath(rel_posix)
    parts = path.parts
    for pattern in patterns:
        cleaned = pattern.rstrip("/")
        if pattern.endswith("/"):
            # Directory pattern: match the directory itself or any descendant.
            if any(fnmatch.fnmatch(part, cleaned) for part in parts):
                return True
            if fnmatch.fnmatch(rel_posix, cleaned) or fnmatch.fnmatch(
                rel_posix, f"{cleaned}/**"
            ):
                return True
            continue
        if fnmatch.fnmatch(path.name, cleaned) or fnmatch.fnmatch(rel_posix, cleaned):
            return True
        if any(fnmatch.fnmatch(part, cleaned) for part in parts):
            return True
    return False


def test_dockerfile_uses_generic_runtime_copy():
    content = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY . ." in content
    # Fragile whitelist that previously omitted generation_jobs must stay gone.
    assert "COPY strategy ./strategy/" not in content
    assert "COPY generation_jobs" not in content


def test_compose_builds_backend_from_backend_context():
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "context: ./backend" in text
    assert "dockerfile: Dockerfile" in text


def test_required_runtime_packages_exist_on_disk():
    for name in REQUIRED_RUNTIME_PACKAGES:
        package_dir = BACKEND_ROOT / name
        assert package_dir.is_dir(), f"missing package directory: {name}"
        assert (package_dir / "__init__.py").is_file(), f"missing {name}/__init__.py"


def test_dockerignore_does_not_exclude_runtime_packages():
    patterns = _dockerignore_lines()
    for name in REQUIRED_RUNTIME_PACKAGES:
        assert name not in patterns, f".dockerignore excludes runtime package {name}"
        assert f"{name}/" not in patterns
        assert f"**/{name}" not in patterns
        assert f"**/{name}/" not in patterns
        assert not _path_ignored(f"{name}/__init__.py", patterns)
        assert not _path_ignored(f"{name}/exceptions.py", patterns)


def test_dockerignore_excludes_secrets_tests_and_local_dbs():
    patterns = set(_dockerignore_lines())
    for expected in MUST_EXCLUDE_PATTERNS:
        assert expected in patterns, f".dockerignore missing exclusion: {expected}"

    lines = _dockerignore_lines()
    assert _path_ignored(".env", lines)
    assert _path_ignored("tests/test_generation_jobs.py", lines)
    assert _path_ignored("qa/runner.py", lines)
    assert _path_ignored("app.db", lines)
    assert _path_ignored(".venv/lib/python3.12/site-packages/x.py", lines)
    assert _path_ignored("__pycache__/main.cpython-312.pyc", lines)


def test_build_context_would_include_generation_jobs():
    """Simulate COPY . . after .dockerignore — generation_jobs must remain."""
    patterns = _dockerignore_lines()
    package_root = BACKEND_ROOT / "generation_jobs"
    included = []
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        if not _path_ignored(rel, patterns):
            included.append(rel)
    assert "generation_jobs/__init__.py" in included
    assert "generation_jobs/exceptions.py" in included
    assert "generation_jobs/worker.py" in included


def test_generation_jobs_package_importable():
    import generation_jobs
    import generation_jobs.exceptions
    import generation_jobs.models
    import generation_jobs.service
    import generation_jobs.worker

    assert generation_jobs is not None
    assert generation_jobs.exceptions is not None
    assert generation_jobs.models is not None
    assert generation_jobs.service is not None
    assert generation_jobs.worker is not None


def test_strategy_package_importable():
    from strategy import (
        StrategyBuilder,
        StrategyComplianceError,
        build_strategy_prompt_section,
        validate_menu_against_strategy,
    )
    from strategy.compliance import validate_menu_against_strategy as compliance_fn
    from strategy.prompt import strategy_to_prompt_dict

    assert StrategyBuilder is not None
    assert StrategyComplianceError is not None
    assert build_strategy_prompt_section is not None
    assert validate_menu_against_strategy is compliance_fn
    assert strategy_to_prompt_dict is not None
