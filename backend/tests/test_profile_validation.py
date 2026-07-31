"""Tests for profile validation helpers."""

from __future__ import annotations

from profile_validation import validate_profile_for_generation, validate_profile_payload


def _valid_profile() -> dict[str, object]:
    return {
        "goal": "home",
        "days": 5,
        "budget": 3000,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "proteins": ["any"],
        "cooktime": "medium",
        "allergies": "нет",
        "store": "any",
        "persons": 2,
    }


def test_valid_profile_payload():
    result = validate_profile_payload(_valid_profile())
    assert result.status == "valid"


def test_days_above_seven_rejected_for_new_write():
    profile = _valid_profile()
    profile["days"] = 8
    result = validate_profile_payload(profile)
    assert result.status == "invalid"
    assert result.field == "days"


def test_budget_bounds_are_shared_with_frontend_contract():
    for budget in (499, 50_001):
        profile = _valid_profile()
        profile["budget"] = budget
        result = validate_profile_payload(profile)
        assert result.status == "invalid"
        assert result.field == "budget"

    for budget in (500, 50_000):
        profile = _valid_profile()
        profile["budget"] = budget
        assert validate_profile_payload(profile).status == "valid"


def test_empty_proteins_incomplete():
    profile = _valid_profile()
    profile["proteins"] = []
    result = validate_profile_payload(profile)
    assert result.status == "incomplete"
    assert result.code == "PROFILE_PROTEIN_REQUIRED"


def test_any_with_specific_invalid():
    profile = _valid_profile()
    profile["proteins"] = ["any", "fish"]
    result = validate_profile_payload(profile)
    assert result.status == "invalid"
    assert result.code == "PROFILE_ANY_WITH_SPECIFIC_PROTEINS"


def test_protein_excluded_invalid():
    profile = _valid_profile()
    profile["proteins"] = ["fish"]
    profile["allergies"] = "рыба"
    result = validate_profile_payload(profile)
    assert result.status == "invalid"
    assert result.code == "PROFILE_PROTEIN_EXCLUDED"


def test_generation_blocks_empty_proteins():
    profile = _valid_profile()
    profile["proteins"] = []
    result = validate_profile_for_generation(profile)
    assert result.status == "incomplete"
    assert result.code == "PROFILE_PROTEIN_REQUIRED"
