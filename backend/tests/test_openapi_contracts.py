"""Targeted OpenAPI schema contract tests."""

from __future__ import annotations

from main import app


def _request_schema(path: str, method: str) -> dict:
    openapi = app.openapi()
    return openapi["paths"][path][method]["requestBody"]["content"]["application/json"]["schema"]


def _ref_schema(name: str) -> dict:
    return app.openapi()["components"]["schemas"][name]


def test_generate_request_schema_token_only():
    schema = _ref_schema("GenerateMenuRequest")
    assert set(schema.get("properties", {})) == {"preview_token"}
    assert schema.get("additionalProperties") is False


def test_preview_request_schema_runtime_only():
    schema = _ref_schema("StrategyPreviewRequest")
    assert set(schema.get("properties", {})) == {"plan_start_date"}
    assert schema.get("additionalProperties") is False


def test_resolve_request_schema_server_owned():
    schema = _ref_schema("ResolveConflictRequest")
    assert set(schema.get("properties", {})) == {"preview_token", "conflict_id", "action"}
    assert schema.get("additionalProperties") is False
    required = set(schema.get("required", []))
    assert required == {"preview_token", "conflict_id", "action"}


def test_compare_request_schema_runtime_only():
    schema = _ref_schema("StrategyCompareRequest")
    assert set(schema.get("properties", {})) == {"plan_start_date"}
    assert schema.get("additionalProperties") is False


def test_compare_response_schema_has_preview_and_diff():
    schema = _ref_schema("StrategyCompareResponse")
    assert "preview" in schema.get("properties", {})
    assert "diff" in schema.get("properties", {})


def test_settings_diff_schema():
    schema = _ref_schema("StrategySettingsDiff")
    props = schema.get("properties", {})
    assert "has_changes" in props
    assert "changes" in props
    assert "comparison_quality" in props


def test_profile_put_schema_has_expected_revision():
    schema = _ref_schema("UpdateProfileRequest")
    props = schema.get("properties", {})
    assert "expected_revision" in props
    assert "dietary_constraints" in props
    assert "allergies" not in props


def test_profile_put_schema_dietary_constraint_input():
    schema = _ref_schema("DietaryConstraintInput")
    assert set(schema.get("properties", {})) == {"id", "kind", "value"}
    kind_schema = schema["properties"]["kind"]
    assert {"$ref" in kind_schema or "enum" in kind_schema}


def test_resolve_action_enum_updated():
    schema = _ref_schema("ConflictResolutionAction")
    values = set(schema.get("enum", []))
    assert "remove_profile_preference" in values
    assert "remove_profile_exclusion" not in values


def test_profile_response_schema_metadata():
    schema = _ref_schema("ProfileResponse")
    props = set(schema.get("properties", {}))
    assert {"profile", "revision", "legacy_constraints", "requires_constraint_review"}.issubset(
        props
    )


def test_api_error_response_schema_present():
    schema = _ref_schema("ApiErrorResponse")
    assert set(schema.get("properties", {})) == {
        "code",
        "message",
        "details",
        "field_errors",
        "request_id",
    }


def test_profile_put_schema_cooking_preferences():
    schema = _ref_schema("UpdateProfileRequest")
    assert "cooking_preferences" in schema.get("properties", {})


def test_legacy_get_profile_endpoint_absent():
    openapi = app.openapi()
    assert "/api/get-profile" not in openapi["paths"]


def test_promote_memory_signal_request_schema():
    schema = _ref_schema("PromoteMemorySignalRequest")
    assert set(schema.get("properties", {})) == {"expected_profile_revision"}
    assert schema.get("additionalProperties") is False
    assert schema.get("required") == ["expected_profile_revision"]


def test_promote_memory_signal_response_schema():
    schema = _ref_schema("PromoteMemorySignalResponse")
    props = set(schema.get("properties", {}))
    assert {"status", "profile", "profile_revision", "signal_status"}.issubset(props)


def test_resolve_response_schema():
    schema = _ref_schema("ResolveConflictResponse")
    props = set(schema.get("properties", {}))
    assert {"status", "requires_new_preview"}.issubset(props)
