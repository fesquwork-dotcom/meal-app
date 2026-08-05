"""Shared domain finalize for catalog MenuPlan (no Claude)."""

from __future__ import annotations

import logging
from typing import Any

from cooking_identity import assign_and_validate_cooking_instances
from menu_generation.errors import CatalogGenerationError
from menu_metadata_normalize import normalize_cooking_leftover_metadata
from menu_models import MenuPlan
from menu_validation import (
    MenuValidationRequest,
    normalize_total_cost,
    validate_menu_plan,
    validate_shopping_budget,
)
from recipe_identity import assign_and_validate_recipe_ids
from shopping.basket_builder import build_basket_from_menu
from shopping.budget_utilization import compute_budget_utilization
from strategy.compliance import validate_menu_against_strategy
from strategy.exceptions import StrategyComplianceError
from strategy.models import WeeklyStrategy
from claude_exceptions import MenuConstraintError

logger = logging.getLogger(__name__)

PLANNER_VERSION = "10.11.2"


def _issues_to_details(issues: list) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for issue in issues[:24]:
        out.append(
            {
                "code": getattr(issue, "code", None),
                "message": getattr(issue, "message", str(issue)),
                "path": getattr(issue, "path", None),
            }
        )
    return out


def finalize_catalog_menu_plan(
    menu_plan: MenuPlan,
    *,
    request: MenuValidationRequest,
    strategy: WeeklyStrategy,
    planner_score: float | None = None,
    planning_duration_ms: float | None = None,
    catalog_recipe_count: int | None = None,
    meal_count: int | None = None,
    leftover_count: int | None = None,
    cooking_instance_count: int | None = None,
    unique_recipe_count: int | None = None,
    request_id: str | None = None,
    max_extra_cook_days: int = 0,
    cook_day_relaxation: dict[str, Any] | None = None,
    strategy_warnings: list[dict[str, Any]] | None = None,
    explanations: list[str] | None = None,
) -> dict[str, Any]:
    """Validate MenuPlan, rebuild basket, attach generation metadata."""
    strategy_aware = True

    menu_plan, id_issues = assign_and_validate_recipe_ids(
        menu_plan,
        strategy_aware=strategy_aware,
    )
    id_errors = [issue for issue in id_issues if issue.severity == "error"]
    if id_errors:
        raise CatalogGenerationError(
            "Recipe identity validation failed",
            code=CatalogGenerationError.MENUPLAN_VALIDATION_FAILED,
            details={"issues": _issues_to_details(id_errors)},
        )

    menu_plan, _meta_stats = normalize_cooking_leftover_metadata(
        menu_plan,
        request_id=request_id,
    )

    menu_plan, cooking_issues = assign_and_validate_cooking_instances(
        menu_plan,
        strategy_aware=strategy_aware,
    )
    cooking_errors = [issue for issue in cooking_issues if issue.severity == "error"]
    if cooking_errors:
        raise CatalogGenerationError(
            "Cooking instance validation failed",
            code=CatalogGenerationError.MENUPLAN_VALIDATION_FAILED,
            details={"issues": _issues_to_details(cooking_errors)},
        )

    menu_plan, cost_normalization = normalize_total_cost(menu_plan)

    validation = validate_menu_plan(
        menu_plan,
        request,
        enforce_user_budget=False,
    )
    if not validation.is_valid:
        raise CatalogGenerationError(
            "Menu constraint validation failed",
            code=CatalogGenerationError.MENUPLAN_VALIDATION_FAILED,
            details={"issues": _issues_to_details(validation.errors)},
        )

    try:
        soft_warnings = validate_menu_against_strategy(
            menu_plan,
            strategy,
            max_extra_cook_days=max_extra_cook_days,
        )
    except StrategyComplianceError as exc:
        raise CatalogGenerationError(
            "Strategy compliance validation failed",
            code=CatalogGenerationError.MENUPLAN_VALIDATION_FAILED,
            details={"issue_codes": list(exc.issue_codes)},
        ) from exc

    try:
        rebuild = build_basket_from_menu(menu_plan, existing_basket=menu_plan.basket or [])
    except Exception as exc:
        logger.exception("catalog_basket_build_failed request_id=%s", request_id)
        raise CatalogGenerationError(
            "Basket build failed",
            code=CatalogGenerationError.BASKET_BUILD_FAILED,
            details={"error_type": type(exc).__name__},
        ) from exc

    menu_plan = menu_plan.model_copy(
        update={
            "basket": rebuild.basket,
            "total_cost": float(rebuild.total_cost or 0),
            "generation_engine": "catalog_planner",
            "planner_version": PLANNER_VERSION,
            "planner_score": planner_score,
            "planning_duration_ms": planning_duration_ms,
        }
    )

    shopping_cost = float(menu_plan.total_cost)
    budget_errors = validate_shopping_budget(shopping_cost, float(request.budget))
    if budget_errors:
        raise CatalogGenerationError(
            "Shopping budget validation failed",
            code=CatalogGenerationError.MENUPLAN_VALIDATION_FAILED,
            details={
                "issues": _issues_to_details(budget_errors),
                "shopping_cost": shopping_cost,
                "budget_limit": float(request.budget),
            },
        )

    # Ensure basket is non-empty for MenuPlan wire contract.
    if not menu_plan.basket:
        from menu_models import BasketCategory, BasketItem

        menu_plan = menu_plan.model_copy(
            update={
                "basket": [
                    BasketCategory(
                        category="Продукты",
                        items=[BasketItem(name="—", weight="", price=0.0)],
                    )
                ],
                "total_cost": 0.0,
            }
        )

    payload = menu_plan.model_dump(mode="json")
    if cost_normalization.model_total is not None:
        payload["model_total"] = float(cost_normalization.model_total)
    if cost_normalization.calculated_total is not None:
        payload["calculated_total"] = float(cost_normalization.calculated_total)

    utilization = compute_budget_utilization(menu_plan, float(strategy.budget))
    if utilization is not None:
        payload.update(utilization.as_wire_fields())

    payload["generation_engine"] = "catalog_planner"
    payload["planner_version"] = PLANNER_VERSION
    if planner_score is not None:
        payload["planner_score"] = float(planner_score)
    if planning_duration_ms is not None:
        payload["planning_duration_ms"] = float(planning_duration_ms)
    if catalog_recipe_count is not None:
        payload["catalog_recipe_count"] = int(catalog_recipe_count)
    if meal_count is not None:
        payload["meal_count"] = int(meal_count)
    if leftover_count is not None:
        payload["leftover_count"] = int(leftover_count)
    if cooking_instance_count is not None:
        payload["cooking_instance_count"] = int(cooking_instance_count)
    if unique_recipe_count is not None:
        payload["unique_recipe_count"] = int(unique_recipe_count)

    merged_warnings = list(strategy_warnings or [])
    for issue in soft_warnings or []:
        merged_warnings.append(
            {
                "code": issue.code,
                "message": issue.message,
                "path": issue.path,
            }
        )
    if merged_warnings:
        payload["strategy_warnings"] = merged_warnings
        payload["warnings"] = [w.get("code") for w in merged_warnings if w.get("code")]

    if explanations:
        payload["explanations"] = list(explanations)

    if cook_day_relaxation is not None:
        payload["cook_day_relaxation"] = cook_day_relaxation
        # Flatten key metadata for operators.
        payload["strict_pass_status"] = cook_day_relaxation.get("strict_pass_status")
        payload["relaxation_used"] = cook_day_relaxation.get("relaxation_used")
        payload["extra_cook_days"] = list(
            cook_day_relaxation.get("extra_cook_days") or []
        )
        payload["original_failed_slot"] = cook_day_relaxation.get(
            "original_failed_slot"
        )
        payload["original_diagnostics"] = cook_day_relaxation.get(
            "original_diagnostics"
        )

    return payload


def map_menu_constraint_error(exc: MenuConstraintError) -> CatalogGenerationError:
    return CatalogGenerationError(
        str(exc) or "Menu constraint validation failed",
        code=CatalogGenerationError.MENUPLAN_VALIDATION_FAILED,
        details={
            "issue_codes": list(getattr(exc, "issue_codes", None) or []),
        },
    )
