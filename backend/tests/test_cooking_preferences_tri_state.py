"""Tests for tri-state cooking preferences (Sprint 5.23)."""

from __future__ import annotations

import json

from cooking_preferences import (
    CookingPreferences,
    cooking_preferences_from_json,
    cooking_preferences_to_db_json,
    cooking_preferences_to_response_dict,
    parse_cooking_preferences,
    serialize_cooking_preferences_json,
)
from strategy.fingerprint import compute_profile_hash


def test_explicit_null_db_json():
    profile = {"cooking_preferences": {"prefer_faster_meals": None}}
    raw = cooking_preferences_to_db_json(profile)
    assert raw is not None
    assert json.loads(raw) == {"prefer_faster_meals": None}


def test_absent_cooking_preferences_not_serialized():
    assert cooking_preferences_to_db_json({}) is None


def test_response_dict_explicit_null():
    raw = json.dumps({"prefer_faster_meals": None})
    assert cooking_preferences_to_response_dict(raw) == {"prefer_faster_meals": None}


def test_response_dict_legacy_null_column():
    assert cooking_preferences_to_response_dict(None) is None


def test_hash_distinguishes_tri_state():
    base = {"goal": "home", "days": 5, "cooktime": "medium", "proteins": ["any"]}
    automatic = compute_profile_hash(
        {**base, "cooking_preferences": {"prefer_faster_meals": None}}
    )
    faster = compute_profile_hash(
        {**base, "cooking_preferences": {"prefer_faster_meals": True}}
    )
    ignore = compute_profile_hash(
        {**base, "cooking_preferences": {"prefer_faster_meals": False}}
    )
    assert len({automatic, faster, ignore}) == 3


def test_parse_explicit_null_in_profile():
    prefs = parse_cooking_preferences({"cooking_preferences": {"prefer_faster_meals": None}})
    assert prefs.prefer_faster_meals is None


def test_from_json_explicit_null():
    raw = json.dumps({"prefer_faster_meals": None})
    prefs = cooking_preferences_from_json(raw)
    assert prefs.prefer_faster_meals is None


def test_serialize_true_still_works():
    raw = serialize_cooking_preferences_json(CookingPreferences(prefer_faster_meals=True))
    assert json.loads(raw) == {"prefer_faster_meals": True}
