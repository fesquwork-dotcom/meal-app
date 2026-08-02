"""Sprint 10.5.5 — Budget Optimizer convergence helpers."""

from __future__ import annotations

from shopping.budget_utilization import (
    MAX_BUDGET_OPTIMIZER_CORRECTIONS,
    build_budget_optimizer_feedback,
    build_budget_optimizer_prompt,
    compute_budget_optimization_target,
    improvement_is_negligible,
    is_better_budget_candidate,
    is_shopping_in_target,
    is_shopping_within_budget,
    should_start_budget_optimizer,
    shopping_cost_from_menu,
    usage_percent_from_shopping,
)


def test_retry_bound_is_two():
    assert MAX_BUDGET_OPTIMIZER_CORRECTIONS == 2


def test_should_start_at_56_percent_not_at_92():
    assert should_start_budget_optimizer(2803.67, 5000) is True
    assert should_start_budget_optimizer(4600, 5000) is False
    assert should_start_budget_optimizer(5000, 5000) is False


def test_target_math_for_5000_budget():
    target = compute_budget_optimization_target(2803.67, 5000)
    assert target is not None
    assert target.min_target == 4500.0
    assert target.preferred_target == 4750.0
    assert target.max_target == 5000.0
    assert abs(target.desired_delta - (4750.0 - 2803.67)) < 0.02
    assert target.underutilized is True


def test_accept_candidate_in_92_98_band():
    assert is_shopping_in_target(4600, 5000)
    assert is_better_budget_candidate(
        candidate_shopping=4600,
        baseline_shopping=2803.67,
        budget_limit=5000,
    )


def test_reject_over_budget_119_percent():
    assert not is_shopping_within_budget(5930, 5000)
    assert not is_better_budget_candidate(
        candidate_shopping=5930,
        baseline_shopping=2803.67,
        budget_limit=5000,
    )


def test_second_candidate_closer_to_preferred_wins():
    # First underutilized, second closer to 95%
    assert is_better_budget_candidate(
        candidate_shopping=4700,
        baseline_shopping=2803.67,
        budget_limit=5000,
    )


def test_baseline_retained_when_candidate_farther_from_preferred():
    # Both under budget; baseline closer to 95% than a worse underutilized bump
    assert not is_better_budget_candidate(
        candidate_shopping=3000,
        baseline_shopping=4700,
        budget_limit=5000,
    )


def test_shopping_cost_authority_over_model_total_fields():
    payload = {
        "total_cost": 4985,
        "shopping_cost": 2803.67,
        "budget_usage_percent": 56.1,
    }
    assert shopping_cost_from_menu(payload) == 2803.67
    assert usage_percent_from_shopping(2803.67, 5000) == 56.1


def test_optimizer_prompt_includes_explicit_targets_and_leftover_guard():
    target = compute_budget_optimization_target(2803.67, 5000)
    prompt = build_budget_optimizer_prompt(
        budget_limit=5000,
        shopping_cost=2803.67,
        target=target,
    )
    assert "4500" in prompt
    assert "4750" in prompt
    assert "LEFTOVER_SOURCE_INGREDIENT_MISSING" in prompt
    assert "порции" in prompt
    assert "shopping_cost" in prompt


def test_feedback_mentions_overshoot_and_leftover_codes():
    text = build_budget_optimizer_feedback(
        budget_limit=5000,
        previous_shopping_cost=5930,
        overshoot_amount=930,
        issue_codes=["BUDGET_EXCEEDED", "LEFTOVER_SOURCE_INGREDIENT_MISSING"],
        reason="menu_constraint",
    )
    assert "5930" in text
    assert "930" in text
    assert "LEFTOVER_SOURCE_INGREDIENT_MISSING" in text
    assert "90–100%" in text or "90-100%" in text.replace("–", "-")


def test_negligible_improvement_detection():
    assert improvement_is_negligible(
        previous_shopping=2803.67,
        new_shopping=2850,
        budget_limit=5000,
    )
    assert not improvement_is_negligible(
        previous_shopping=2803.67,
        new_shopping=4600,
        budget_limit=5000,
    )
