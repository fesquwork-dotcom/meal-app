"""Dismissal is durable until a future Learning rule version."""

from learning_test_helpers import seed_learning_candidate
from test_learning_api import client  # noqa: F401


def test_dismiss_hides_and_never_recreates_same_rule_version(client):
    seed_learning_candidate(client)
    recommendation = client.get("/api/learning/recommendations").json()[
        "recommendations"
    ][0]
    response = client.post(
        f"/api/learning/recommendations/{recommendation['recommendation_id']}/dismiss"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"

    for _ in range(3):
        listed = client.get("/api/learning/recommendations").json()
        assert listed["candidate_count"] == 0
        assert listed["recommendations"] == []


def test_dismiss_is_idempotent(client):
    seed_learning_candidate(client)
    recommendation_id = client.get("/api/learning/recommendations").json()[
        "recommendations"
    ][0]["recommendation_id"]
    url = f"/api/learning/recommendations/{recommendation_id}/dismiss"
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 200
