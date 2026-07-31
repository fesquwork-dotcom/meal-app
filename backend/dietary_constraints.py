"""Dietary constraints domain model (Sprint 5.20).

Separates safety constraints (allergy, intolerance) from preference-based
exclusions and models legacy unspecified exclusions safely. No medical
classification is performed here: the constraint kind is always chosen
explicitly by the user.
"""

from __future__ import annotations

import json
import re
import secrets
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shopping.normalization import canonical_ingredient_name

MAX_DIETARY_CONSTRAINTS = 50
MAX_CONSTRAINT_VALUE_LENGTH = 64
CONSTRAINT_ID_PATTERN = re.compile(r"^dc_[0-9a-f]{12,24}$")

# Internal-only kind for unclassified legacy exclusions. Never accepted as
# input and never persisted into dietary_constraints_json.
LEGACY_KIND = "legacy"


class DietaryConstraintKind(str, Enum):
    ALLERGY = "allergy"
    INTOLERANCE = "intolerance"
    PREFERENCE = "preference"


SAFETY_KINDS = frozenset(
    {DietaryConstraintKind.ALLERGY.value, DietaryConstraintKind.INTOLERANCE.value}
)

# Lower number wins on canonical-value collisions (safety-first merge).
KIND_PRIORITY: dict[str, int] = {
    DietaryConstraintKind.ALLERGY.value: 0,
    DietaryConstraintKind.INTOLERANCE.value: 1,
    LEGACY_KIND: 2,
    DietaryConstraintKind.PREFERENCE.value: 3,
}


ConstraintSource = Literal["manual", "memory"]


class DietaryConstraint(BaseModel):
    """Persisted typed dietary constraint owned by the backend."""

    model_config = ConfigDict(extra="ignore")

    id: str
    kind: DietaryConstraintKind
    value: str
    canonical_value: str
    source: ConstraintSource = "manual"


class DietaryConstraintInput(BaseModel):
    """Constraint payload accepted from Profile PUT."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    kind: DietaryConstraintKind
    value: str = Field(min_length=1, max_length=MAX_CONSTRAINT_VALUE_LENGTH)


class DietaryConstraintError(ValueError):
    """Raised when constraint input violates the domain contract."""

    def __init__(self, message: str, *, code: str, field: str = "dietary_constraints") -> None:
        super().__init__(message)
        self.code = code
        self.field = field


def new_constraint_id() -> str:
    return f"dc_{secrets.token_hex(8)}"


def is_valid_constraint_id(value: str) -> bool:
    return bool(value) and bool(CONSTRAINT_ID_PATTERN.match(value))


def canonical_constraint_value(value: str) -> str:
    """Canonical key reusing the shared ingredient normalization (trim,
    lowercase, ё→е, aliases, whitespace collapse)."""
    return canonical_ingredient_name(value)


def _clean_display_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_constraints(
    inputs: list[DietaryConstraintInput],
    *,
    existing: list[DietaryConstraint] | None = None,
) -> list[DietaryConstraint]:
    """Validates and deduplicates constraint inputs into persisted constraints.

    Rules:
    - empty values rejected;
    - value length capped;
    - max constraints capped;
    - same-kind canonical duplicates collapse into one;
    - on cross-kind collisions the safety kind wins (allergy > intolerance > preference);
    - IDs are preserved when the client sends a known ID, otherwise assigned
      by the backend. IDs never derive from the display text.
    """
    if len(inputs) > MAX_DIETARY_CONSTRAINTS:
        raise DietaryConstraintError(
            f"Too many dietary constraints (max {MAX_DIETARY_CONSTRAINTS})",
            code="PROFILE_TOO_MANY_CONSTRAINTS",
        )

    existing_by_id = {item.id: item for item in (existing or [])}
    best_by_canonical: dict[str, DietaryConstraint] = {}

    for item in inputs:
        display = _clean_display_value(item.value)
        if not display:
            raise DietaryConstraintError(
                "Constraint value must not be empty",
                code="PROFILE_CONSTRAINT_VALUE_EMPTY",
            )
        canonical = canonical_constraint_value(display)
        if not canonical:
            raise DietaryConstraintError(
                "Constraint value must not be empty",
                code="PROFILE_CONSTRAINT_VALUE_EMPTY",
            )

        constraint_id = item.id
        if constraint_id is not None:
            if not is_valid_constraint_id(constraint_id):
                raise DietaryConstraintError(
                    "Constraint ID format is invalid",
                    code="PROFILE_CONSTRAINT_ID_INVALID",
                )
            if constraint_id not in existing_by_id:
                # Unknown IDs are not trusted; backend assigns a fresh one.
                constraint_id = new_constraint_id()
        else:
            constraint_id = new_constraint_id()

        # Sprint 10.1: intolerance remains wire-compatible for old clients,
        # but all new persistence uses the single user-facing safety kind.
        persisted_kind = (
            DietaryConstraintKind.ALLERGY
            if item.kind == DietaryConstraintKind.INTOLERANCE
            else item.kind
        )
        candidate = DietaryConstraint(
            id=constraint_id,
            kind=persisted_kind,
            value=display,
            canonical_value=canonical,
        )

        current = best_by_canonical.get(canonical)
        if current is None:
            best_by_canonical[canonical] = candidate
            continue

        # Controlled cross-kind rule: keep the highest-priority (safety) kind.
        if KIND_PRIORITY[candidate.kind.value] < KIND_PRIORITY[current.kind.value]:
            best_by_canonical[canonical] = candidate

    return list(best_by_canonical.values())


def parse_constraints_json(raw: str | None) -> list[DietaryConstraint]:
    """Reads persisted constraints; malformed entries are dropped defensively."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []

    constraints: list[DietaryConstraint] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        try:
            constraints.append(DietaryConstraint.model_validate(entry))
        except Exception:
            continue
    return constraints


def serialize_constraints_json(constraints: list[DietaryConstraint]) -> str:
    return json.dumps(
        [constraint.model_dump(mode="json") for constraint in constraints],
        ensure_ascii=False,
    )


def parse_legacy_allergies(allergies: object) -> list[str]:
    """Parses the deprecated raw allergies string into display values."""
    if not isinstance(allergies, str):
        return []
    stripped = allergies.strip()
    if not stripped or stripped.lower() == "нет":
        return []

    values: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,;]+", stripped):
        display = _clean_display_value(part)
        if not display or display.lower() == "нет":
            continue
        canonical = canonical_constraint_value(display)
        if canonical and canonical not in seen:
            seen.add(canonical)
            values.append(display)
    return values


def serialize_legacy_allergies(values: list[str]) -> str:
    cleaned = [item for item in (_clean_display_value(value) for value in values) if item]
    return ", ".join(cleaned) if cleaned else "нет"


def constraints_from_profile(profile: dict[str, object] | None) -> list[DietaryConstraint]:
    """Reads typed constraints from a normalized profile dict."""
    if not profile:
        return []
    raw = profile.get("dietary_constraints")
    if isinstance(raw, str):
        return parse_constraints_json(raw)
    if not isinstance(raw, list):
        return []

    constraints: list[DietaryConstraint] = []
    for entry in raw:
        if isinstance(entry, DietaryConstraint):
            constraints.append(entry)
            continue
        if isinstance(entry, dict):
            try:
                constraints.append(DietaryConstraint.model_validate(entry))
            except Exception:
                continue
    return constraints


def constraint_counts_by_kind(constraints: list[DietaryConstraint]) -> dict[str, int]:
    """Value-free counts for observability logging."""
    counts: dict[str, int] = {}
    for constraint in constraints:
        counts[constraint.kind.value] = counts.get(constraint.kind.value, 0) + 1
    return counts
