"""Internal resolution metadata for detected strategy conflicts."""

from __future__ import annotations

from dataclasses import dataclass

from strategy.conflict_id import compute_conflict_id
from strategy.preview_models import ConflictResolutionOption, StrategyConflict


@dataclass(frozen=True)
class ConflictResolutionTarget:
    profile_field: str | None = None
    canonical_value: str | None = None
    exclusion_value: str | None = None
    memory_signal_id: str | None = None
    constraint_id: str | None = None


@dataclass(frozen=True)
class DetectedConflict:
    conflict_id: str
    conflict: StrategyConflict
    target: ConflictResolutionTarget
    priority: int


def build_detected_conflict(
    *,
    code: str,
    title: str,
    description: str,
    severity: str,
    field: str | None,
    options: list[ConflictResolutionOption],
    target: ConflictResolutionTarget,
    profile_revision: int,
    preview_version: int,
    priority: int,
) -> DetectedConflict:
    conflict_id = compute_conflict_id(
        code=code,
        field=field,
        canonical_value=target.canonical_value,
        memory_signal_id=target.memory_signal_id,
        profile_revision=profile_revision,
        preview_version=preview_version,
    )
    conflict = StrategyConflict(
        conflict_id=conflict_id,
        code=code,
        title=title,
        description=description,
        severity=severity,  # type: ignore[arg-type]
        field=field,
        options=options,
    )
    return DetectedConflict(
        conflict_id=conflict_id,
        conflict=conflict,
        target=target,
        priority=priority,
    )
