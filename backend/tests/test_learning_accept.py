"""Accept returns an allowlisted patch and never mutates Profile itself."""

from learning_test_helpers import seed_learning_candidate
from profile_test_helpers import save_profile
from test_learning_api import client  # noqa: F401


def test_accept_returns_patch_without_changing_profile(client):
    _strategy_id, revision = seed_learning_candidate(client)
    before = client.get("/api/profile").json()
    recommendation = client.get("/api/learning/recommendations").json()[
        "recommendations"
    ][0]

    response = client.post(
        f"/api/learning/recommendations/{recommendation['recommendation_id']}/accept"
    )
    assert response.status_code == 200
    assert response.json() == {
        "recommendation_id": recommendation["recommendation_id"],
        "status": "accepted",
        "recommended_profile_patch": {
            "planning_preferences": {"prefer_familiar_meals": True},
            "cooking_preferences": None,
            "cooktime": None,
        },
    }
    after = client.get("/api/profile").json()
    assert after["revision"] == revision
    assert after["profile"] == before["profile"]


def test_accept_is_idempotent_and_remains_visible_until_profile_changes(client):
    seed_learning_candidate(client)
    recommendation = client.get("/api/learning/recommendations").json()[
        "recommendations"
    ][0]
    url = (
        f"/api/learning/recommendations/{recommendation['recommendation_id']}/accept"
    )
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 200
    listed = client.get("/api/learning/recommendations").json()
    assert listed["accepted_count"] == 1
    assert listed["recommendations"][0]["status"] == "accepted"


def test_existing_profile_cas_flow_applies_patch_and_expires_recommendation(client):
    _strategy_id, revision = seed_learning_candidate(client)
    recommendation = client.get("/api/learning/recommendations").json()[
        "recommendations"
    ][0]
    accepted = client.post(
        f"/api/learning/recommendations/{recommendation['recommendation_id']}/accept"
    ).json()

    # This is the same separate PUT the frontend performs after human consent.
    saved = save_profile(
        client,
        expected_revision=revision,
        planning_preferences=accepted["recommended_profile_patch"][
            "planning_preferences"
        ],
        cooking_preferences={"prefer_faster_meals": False},
    )
    assert saved.status_code == 200
    assert saved.json()["revision"] == revision + 1
    assert saved.json()["profile"]["planning_preferences"] == {
        "prefer_familiar_meals": True
    }

    listed = client.get("/api/learning/recommendations").json()
    assert listed["recommendations"] == []
