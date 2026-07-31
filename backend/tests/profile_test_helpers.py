"""Shared profile API test helpers."""

from __future__ import annotations

VALID_PROFILE_BODY = {
    "days": 3,
    "budget": 3000,
    "proteins": ["any"],
    "goal": "home",
    "meal_types": ["breakfast", "lunch", "dinner"],
    "meals_per_day": 3,
    "persons": 2,
    "cooktime": "medium",
    "dietary_constraints": [],
    "legacy_allergies": [],
    "store": "any",
}


def save_profile(client, *, expected_revision: int = 0, **overrides):
    body = {**VALID_PROFILE_BODY, **overrides, "expected_revision": expected_revision}
    return client.put("/api/profile", json=body)


def preview_strategy(client, *, plan_start_date: str | None = None):
    body: dict[str, str] = {}
    if plan_start_date is not None:
        body["plan_start_date"] = plan_start_date
    return client.post("/api/strategy/preview", json=body)


def issue_preview_token(client, *, plan_start_date: str | None = None) -> str:
    response = preview_strategy(client, plan_start_date=plan_start_date)
    assert response.status_code == 200, response.text
    token = response.json().get("preview_token")
    assert token
    return token


def generate_with_token(client, preview_token: str):
    return client.post("/api/generate-menu", json={"preview_token": preview_token})
