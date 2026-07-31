"""Learning API exposes templates and aggregate conclusions only."""

from learning_test_helpers import seed_learning_candidate
from test_learning_api import client  # noqa: F401


def test_list_and_accept_do_not_leak_internal_evidence(client):
    strategy_id, _revision = seed_learning_candidate(client)
    response = client.get("/api/learning/recommendations")
    assert response.status_code == 200
    recommendation = response.json()["recommendations"][0]

    accepted = client.post(
        f"/api/learning/recommendations/{recommendation['recommendation_id']}/accept"
    )
    combined = response.text + accepted.text
    for forbidden in (
        strategy_id,
        "private-event",
        "meal-private",
        "recipe-private",
        "private-ingredient",
        "evidence_json",
        "trace_json",
        "event_key",
        "evidence_count",
        "replacement_count",
        "source_strategy_id",
    ):
        assert forbidden not in combined


def test_public_text_does_not_claim_unknown_recipe_novelty(client):
    seed_learning_candidate(client)
    text = client.get("/api/learning/recommendations").text.lower()
    assert "новые рецепты" not in text
    assert "большинство замен приходилось" not in text
