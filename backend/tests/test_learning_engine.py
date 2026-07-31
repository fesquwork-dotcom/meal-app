"""Pure deterministic Learning rules and trust boundaries."""

from decision.outcome import DecisionOutcome, DecisionOutcomeCollection
from learning.engine import LearningEvidence, build_learning_recommendations


def _outcomes(
    *,
    familiar_status: str = "unsuccessful",
    familiar_result: str = "high_replacement_rate",
    faster_status: str = "pending",
    faster_result: str = "evaluation_not_supported",
) -> DecisionOutcomeCollection:
    return DecisionOutcomeCollection(
        outcomes=[
            DecisionOutcome(
                decision_key="planning.prefer_familiar_meals",
                result=familiar_result,
                confidence="strong",
                evidence_count=9,
                status=familiar_status,
            ),
            DecisionOutcome(
                decision_key="cooking.prefer_faster",
                result=faster_result,
                confidence="strong",
                evidence_count=3,
                status=faster_status,
            ),
        ]
    )


def _evidence(**overrides) -> LearningEvidence:
    values = {
        "replacement_count": 9,
        "planned_meal_count": 21,
        "faster_replacement_count": 0,
        "suited_meal_count": 0,
        "cooked_meal_count": 0,
        "decision_prefer_familiar": False,
        "decision_prefer_faster": False,
    }
    return LearningEvidence(**{**values, **overrides})


def _profile(*, familiar=False, faster=False):
    return {
        "planning_preferences": {"prefer_familiar_meals": familiar},
        "cooking_preferences": {"prefer_faster_meals": faster},
        "cooktime": "medium",
    }


def test_recommends_enabling_familiar_meals_after_failed_disabled_decision():
    result = build_learning_recommendations(
        _outcomes(), _evidence(), _profile(familiar=False)
    )
    assert len(result.recommendations) == 1
    recommendation = result.recommendations[0]
    assert (
        recommendation.recommendation_type
        == "profile_enable_prefer_familiar_meals"
    )
    assert (
        recommendation.recommended_profile_patch.planning_preferences.model_dump()
        == {"prefer_familiar_meals": True}
    )


def test_recommends_disabling_familiar_only_without_positive_evidence():
    evidence = _evidence(decision_prefer_familiar=True)
    result = build_learning_recommendations(
        _outcomes(), evidence, _profile(familiar=True)
    )
    assert result.recommendations[0].recommendation_type == (
        "profile_disable_prefer_familiar_meals"
    )

    for positive in (
        _evidence(decision_prefer_familiar=True, suited_meal_count=2),
        _evidence(decision_prefer_familiar=True, plan_completed=True),
    ):
        assert not build_learning_recommendations(
            _outcomes(), positive, _profile(familiar=True)
        ).recommendations


def test_faster_rules_require_time_specific_evidence():
    outcomes = _outcomes(
        familiar_status="pending",
        familiar_result="evaluation_not_supported",
        faster_status="unsuccessful",
        faster_result="faster_replacements_persisted",
    )
    result = build_learning_recommendations(
        outcomes,
        _evidence(faster_replacement_count=3),
        _profile(faster=False),
    )
    assert result.recommendations[0].recommendation_type == (
        "profile_enable_prefer_faster_meals"
    )

    generic = _outcomes(
        familiar_status="pending",
        familiar_result="evaluation_not_supported",
        faster_status="unsuccessful",
        faster_result="high_replacement_rate",
    )
    assert not build_learning_recommendations(
        generic, _evidence(faster_replacement_count=0), _profile(faster=False)
    ).recommendations


def test_profile_change_makes_old_outcome_ineligible():
    # The outcome belongs to a plan where familiar=false. Once Profile is true,
    # that old result cannot justify an opposite recommendation.
    result = build_learning_recommendations(
        _outcomes(),
        _evidence(decision_prefer_familiar=False),
        _profile(familiar=True),
    )
    assert result.recommendations == []


def test_cooking_time_type_is_not_generated_without_time_limit_outcome():
    result = build_learning_recommendations(
        _outcomes(), _evidence(), _profile()
    )
    assert all(
        item.recommendation_type != "profile_adjust_cooking_time"
        for item in result.recommendations
    )


def test_generation_is_deterministic_and_side_effect_free():
    outcomes = _outcomes()
    evidence = _evidence()
    profile = _profile()
    assert build_learning_recommendations(
        outcomes, evidence, profile
    ) == build_learning_recommendations(outcomes, evidence, profile)
    assert profile == _profile()


def test_decision_engine_does_not_import_learning_layer():
    import pathlib

    decision_dir = pathlib.Path(__file__).resolve().parents[1] / "decision"
    for module in ("engine.py", "resolver.py", "builder.py", "context.py"):
        source = (decision_dir / module).read_text(encoding="utf-8")
        assert "learning" not in source
