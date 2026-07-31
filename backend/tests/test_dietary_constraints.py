"""Domain tests for dietary constraints (Sprint 5.20)."""

from __future__ import annotations

import pytest

from dietary_constraints import (
    DietaryConstraint,
    DietaryConstraintError,
    DietaryConstraintInput,
    DietaryConstraintKind,
    canonical_constraint_value,
    is_valid_constraint_id,
    new_constraint_id,
    normalize_constraints,
    parse_legacy_allergies,
    serialize_legacy_allergies,
)


def test_new_constraint_id_format():
    constraint_id = new_constraint_id()
    assert is_valid_constraint_id(constraint_id)
    assert constraint_id.startswith("dc_")


def test_legacy_intolerance_is_persisted_as_allergy():
    inputs = [
        DietaryConstraintInput(kind=DietaryConstraintKind.ALLERGY, value="Арахис"),
        DietaryConstraintInput(kind=DietaryConstraintKind.INTOLERANCE, value="молоко"),
        DietaryConstraintInput(kind=DietaryConstraintKind.PREFERENCE, value="рыба"),
    ]
    result = normalize_constraints(inputs)
    assert len(result) == 3
    kinds = {item.kind for item in result}
    assert kinds == {
        DietaryConstraintKind.ALLERGY,
        DietaryConstraintKind.PREFERENCE,
    }
    assert next(item for item in result if item.value == "молоко").kind == DietaryConstraintKind.ALLERGY


def test_safety_beats_preference_on_same_canonical():
    inputs = [
        DietaryConstraintInput(kind=DietaryConstraintKind.PREFERENCE, value="арахис"),
        DietaryConstraintInput(kind=DietaryConstraintKind.ALLERGY, value="Арахис"),
    ]
    result = normalize_constraints(inputs)
    assert len(result) == 1
    assert result[0].kind == DietaryConstraintKind.ALLERGY


def test_legacy_intolerance_projects_to_allergy_and_beats_preference():
    inputs = [
        DietaryConstraintInput(kind=DietaryConstraintKind.PREFERENCE, value="молоко"),
        DietaryConstraintInput(kind=DietaryConstraintKind.INTOLERANCE, value="Молоко"),
    ]
    result = normalize_constraints(inputs)
    assert len(result) == 1
    assert result[0].kind == DietaryConstraintKind.ALLERGY


def test_duplicate_same_kind_collapses():
    inputs = [
        DietaryConstraintInput(kind=DietaryConstraintKind.ALLERGY, value="арахис"),
        DietaryConstraintInput(kind=DietaryConstraintKind.ALLERGY, value="Арахис"),
    ]
    result = normalize_constraints(inputs)
    assert len(result) == 1


def test_empty_value_rejected():
    with pytest.raises(DietaryConstraintError) as exc:
        normalize_constraints(
            [DietaryConstraintInput(kind=DietaryConstraintKind.PREFERENCE, value="   ")]
        )
    assert exc.value.code == "PROFILE_CONSTRAINT_VALUE_EMPTY"


def test_max_constraints_rejected():
    inputs = [
        DietaryConstraintInput(kind=DietaryConstraintKind.PREFERENCE, value=f"item{i}")
        for i in range(51)
    ]
    with pytest.raises(DietaryConstraintError) as exc:
        normalize_constraints(inputs)
    assert exc.value.code == "PROFILE_TOO_MANY_CONSTRAINTS"


def test_preserve_existing_id():
    existing = [
        DietaryConstraint(
            id="dc_aabbccddeeff",
            kind=DietaryConstraintKind.ALLERGY,
            value="арахис",
            canonical_value="арахис",
        )
    ]
    inputs = [
        DietaryConstraintInput(
            id="dc_aabbccddeeff",
            kind=DietaryConstraintKind.ALLERGY,
            value="арахис",
        )
    ]
    result = normalize_constraints(inputs, existing=existing)
    assert result[0].id == "dc_aabbccddeeff"


def test_canonical_aliases():
    assert canonical_constraint_value("Помидоры") == canonical_constraint_value("томаты")


def test_parse_legacy_allergies():
    assert parse_legacy_allergies("нет") == []
    assert parse_legacy_allergies("арахис, сельдерей") == ["арахис", "сельдерей"]
    assert serialize_legacy_allergies(["арахис"]) == "арахис"
    assert serialize_legacy_allergies([]) == "нет"


def test_normalize_does_not_mutate_inputs():
    inputs = [
        DietaryConstraintInput(kind=DietaryConstraintKind.PREFERENCE, value="рыба"),
    ]
    snapshot = [item.model_dump() for item in inputs]
    normalize_constraints(inputs)
    assert [item.model_dump() for item in inputs] == snapshot
