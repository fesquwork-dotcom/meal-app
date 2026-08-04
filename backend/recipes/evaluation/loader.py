"""Load and validate evaluation scenario YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from recipes.evaluation.models import EvaluationScenario

DEFAULT_EVALUATION_DIR = (
    Path(__file__).resolve().parents[1].parent / "recipe_catalog" / "evaluation"
)


class ScenarioLoadError(ValueError):
    """Raised when evaluation scenario files are invalid."""


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_scenarios_from_file(path: Path) -> list[EvaluationScenario]:
    raw = _load_yaml(path)
    if raw is None:
        return []
    if isinstance(raw, dict) and "scenarios" in raw:
        items = raw["scenarios"]
    elif isinstance(raw, list):
        items = raw
    else:
        raise ScenarioLoadError(f"Invalid scenario file structure: {path}")
    if not isinstance(items, list):
        raise ScenarioLoadError(f"'scenarios' must be a list in {path}")

    scenarios: list[EvaluationScenario] = []
    for idx, item in enumerate(items):
        try:
            scenarios.append(EvaluationScenario.model_validate(item))
        except ValidationError as exc:
            raise ScenarioLoadError(
                f"Invalid scenario at index {idx} in {path}: {exc}"
            ) from exc
    return scenarios


def load_evaluation_scenarios(
    evaluation_dir: Path | None = None,
    *,
    scenario_file: Path | None = None,
    group: str | None = None,
    include_disabled: bool = False,
) -> list[EvaluationScenario]:
    if scenario_file is not None:
        scenarios = load_scenarios_from_file(Path(scenario_file))
    else:
        root = Path(evaluation_dir) if evaluation_dir else DEFAULT_EVALUATION_DIR
        if not root.is_dir():
            raise ScenarioLoadError(f"Evaluation directory not found: {root}")
        files = sorted(root.glob("*_scenarios.yaml"))
        if not files:
            raise ScenarioLoadError(f"No *_scenarios.yaml files in {root}")
        scenarios = []
        for path in files:
            scenarios.extend(load_scenarios_from_file(path))

    ids = [s.id for s in scenarios]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ScenarioLoadError(f"Duplicate scenario ids: {dupes}")

    if not include_disabled:
        scenarios = [s for s in scenarios if s.enabled]

    if group is not None:
        scenarios = [s for s in scenarios if s.scenario_group.value == group]

    scenarios.sort(key=lambda s: (s.scenario_group.value, s.id))
    return scenarios
