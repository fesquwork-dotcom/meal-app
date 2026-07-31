"""Weekly strategy engine — deterministic planning decisions before LLM execution."""

from strategy.builder import StrategyBuilder
from strategy.compliance import validate_menu_against_strategy
from strategy.cooking_compliance import validate_cooking_contract
from strategy.exceptions import (
    StrategyComplianceError,
    StrategyNotFoundError,
    StrategyPersistenceError,
    StrategyValidationError,
    UnsupportedStrategyVersionError,
)
from strategy.models import WeeklyStrategy
from strategy.repository import StrategyRepository
from strategy.service import StrategyService
from strategy.planner_input import PlannerInput, build_planner_input
from strategy.prompt import (
    build_correction_prompt,
    build_strategy_prompt_section,
    build_strategy_system_section,
    build_targeted_correction_prompt,
    strategy_to_prompt_dict,
)
from strategy.validation import validate_strategy_for_request

__all__ = [
    "StrategyBuilder",
    "StrategyComplianceError",
    "StrategyNotFoundError",
    "StrategyPersistenceError",
    "StrategyRepository",
    "StrategyService",
    "StrategyValidationError",
    "UnsupportedStrategyVersionError",
    "WeeklyStrategy",
    "PlannerInput",
    "build_planner_input",
    "validate_strategy_for_request",
    "validate_menu_against_strategy",
    "validate_cooking_contract",
    "build_strategy_prompt_section",
    "build_strategy_system_section",
    "build_correction_prompt",
    "build_targeted_correction_prompt",
    "strategy_to_prompt_dict",
]
