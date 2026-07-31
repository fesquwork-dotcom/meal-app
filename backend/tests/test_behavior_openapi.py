"""OpenAPI contract tests for behavior insight endpoints."""

from __future__ import annotations

from main import app


def _ref_schema(name: str) -> dict:
    return app.openapi()["components"]["schemas"][name]


def test_behavior_insights_list_endpoint_exists():
    paths = app.openapi()["paths"]
    assert "/api/behavior/insights" in paths
    assert "get" in paths["/api/behavior/insights"]


def test_behavior_confirm_endpoint_exists():
    paths = app.openapi()["paths"]
    assert "/api/behavior/insights/{insight_id}/confirm" in paths
    assert "post" in paths["/api/behavior/insights/{insight_id}/confirm"]


def test_behavior_dismiss_endpoint_exists():
    paths = app.openapi()["paths"]
    assert "/api/behavior/insights/{insight_id}/dismiss" in paths
    assert "post" in paths["/api/behavior/insights/{insight_id}/dismiss"]


def test_behavior_snooze_endpoint_exists():
    paths = app.openapi()["paths"]
    assert "/api/behavior/insights/{insight_id}/snooze" in paths
    assert "post" in paths["/api/behavior/insights/{insight_id}/snooze"]


def test_behavior_revoke_endpoint_exists():
    paths = app.openapi()["paths"]
    assert "/api/behavior/insights/{insight_id}/revoke" in paths
    assert "post" in paths["/api/behavior/insights/{insight_id}/revoke"]


def test_behavior_apply_recommendation_endpoint_exists():
    paths = app.openapi()["paths"]
    assert "/api/behavior/insights/{insight_id}/apply-recommendation" in paths
    assert "post" in paths["/api/behavior/insights/{insight_id}/apply-recommendation"]


def test_apply_recommendation_request_schema():
    schema = _ref_schema("ApplyBehaviorRecommendationRequest")
    assert set(schema.get("properties", {})) == {"expected_profile_revision"}
    assert schema.get("additionalProperties") is False


def test_apply_recommendation_response_schema():
    schema = _ref_schema("ApplyBehaviorRecommendationResponse")
    props = set(schema.get("properties", {}))
    assert props == {"status", "profile", "profile_revision", "recommendation_key"}
    assert schema.get("additionalProperties") is False


def test_behavior_recommendation_response_schema():
    schema = _ref_schema("BehaviorRecommendationResponse")
    assert set(schema.get("properties", {})) == {"key", "can_apply", "applied"}
    assert schema.get("additionalProperties") is False


def test_behavior_snooze_request_schema():
    schema = _ref_schema("BehaviorSnoozeRequest")
    assert set(schema.get("properties", {})) == {"duration"}
    assert schema.get("additionalProperties") is False
    duration = schema["properties"]["duration"]
    ref = duration.get("$ref") or duration.get("anyOf", [{}])[0].get("$ref")
    assert ref is not None


def test_behavior_revoke_response_schema():
    schema = _ref_schema("BehaviorRevokeResponse")
    assert set(schema.get("properties", {})) == {
        "insight",
        "strategy_effect_changed",
        "profile_preference_remains_active",
    }
    assert schema.get("additionalProperties") is False


def test_behavior_insight_response_schema():
    schema = _ref_schema("BehaviorInsightResponse")
    props = set(schema.get("properties", {}))
    assert props == {
        "id",
        "type",
        "status",
        "title",
        "description",
        "evidence_count",
        "confidence",
        "can_confirm",
        "can_dismiss",
        "can_snooze",
        "can_revoke",
        "created_at",
        "updated_at",
        "recommendation",
        "snoozed_until",
        "revoked_at",
    }
    assert "target_key" not in props
    assert "insight_key" not in props
    assert "user_id" not in props
    assert schema.get("additionalProperties") is False


def test_behavior_insights_list_response_schema():
    schema = _ref_schema("BehaviorInsightsListResponse")
    props = set(schema.get("properties", {}))
    assert props == {"insights", "candidate_count", "confirmed_count"}
    assert schema.get("additionalProperties") is False


def test_behavior_action_response_schema():
    schema = _ref_schema("BehaviorInsightActionResponse")
    assert set(schema.get("properties", {})) == {"insight"}
    assert schema.get("additionalProperties") is False


def test_behavior_endpoints_use_api_error_response():
    openapi = app.openapi()
    endpoints = {
        "/api/behavior/insights": "get",
        "/api/behavior/insights/{insight_id}/confirm": "post",
        "/api/behavior/insights/{insight_id}/dismiss": "post",
        "/api/behavior/insights/{insight_id}/snooze": "post",
        "/api/behavior/insights/{insight_id}/revoke": "post",
    }
    for path, method in endpoints.items():
        responses = openapi["paths"][path][method]["responses"]
        for status in ("404", "409", "503"):
            if status in responses:
                schema = responses[status]["content"]["application/json"]["schema"]
                assert schema.get("$ref") == "#/components/schemas/ApiErrorResponse"
