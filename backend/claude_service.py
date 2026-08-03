import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import date
from typing import Optional

import httpx
from pydantic import ValidationError

import config
from anthropic_http import (
    compute_retry_delay_seconds,
    create_anthropic_client,
    is_retryable_anthropic_status,
    parse_anthropic_error,
)
from claude_exceptions import (
    ClaudeJsonError,
    ClaudeOutputTruncatedError,
    ClaudeTimeoutError,
    ClaudeUnavailableError,
    ClaudeValidationError,
    MenuConstraintError,
)
from claude_json import extract_json_object_with_meta
from meal_types import MEAL_TYPE_LABELS_RU, normalize_days_plan_payload
from menu_models import MenuPlan
from cooking_identity import assign_and_validate_cooking_instances
from menu_metadata_normalize import normalize_cooking_leftover_metadata
from recipe_identity import assign_and_validate_recipe_ids
from shopping.basket_builder import build_basket_from_menu
from shopping.budget_utilization import (
    MAX_BUDGET_OPTIMIZER_CORRECTIONS,
    build_budget_optimizer_feedback,
    build_budget_optimizer_prompt,
    compute_budget_optimization_target,
    compute_budget_utilization,
    improvement_is_negligible,
    is_better_budget_candidate,
    is_shopping_in_target,
    is_shopping_within_budget,
    shopping_cost_from_menu,
    should_start_budget_optimizer,
    usage_percent_from_shopping,
)
from menu_validation import (
    MenuValidationRequest,
    build_meal_usage_inventory,
    normalize_total_cost,
    validate_menu_plan,
    validate_shopping_budget,
)
from strategy.compliance import validate_menu_against_strategy
from strategy.exceptions import StrategyComplianceError
from strategy.models import WeeklyStrategy
from strategy.prompt import (
    build_correction_prompt,
    build_strategy_prompt_section,
    build_strategy_system_section,
    build_targeted_correction_prompt,
)

logger = logging.getLogger(__name__)

MAX_LLM_ATTEMPTS = 3
"""Total Claude API calls per generation: 1 initial + up to 2 correction attempts."""

GenerationProgressCallback = Callable[..., Awaitable[None]]


class GenerationReliabilityStats:
    """In-process counters for Sprint 10.7 observability (not API-exposed)."""

    __slots__ = (
        "llm_attempts",
        "local_json_recoveries",
        "json_recovery_failures",
        "metadata_normalizations",
        "correction_count",
    )

    def __init__(self) -> None:
        self.llm_attempts = 0
        self.local_json_recoveries = 0
        self.json_recovery_failures = 0
        self.metadata_normalizations = 0
        self.correction_count = 0

    def summary_kwargs(self) -> dict[str, object]:
        return {
            "llm_attempts": self.llm_attempts,
            "local_json_recoveries": self.local_json_recoveries,
            "metadata_normalizations": self.metadata_normalizations,
            "correction_count": self.correction_count,
        }


async def _emit_generation_progress(
    callback: GenerationProgressCallback | None,
    *,
    stage: str,
    attempt: int | None = None,
    max_attempts: int | None = None,
) -> None:
    if callback is None:
        return
    try:
        await callback(stage=stage, attempt=attempt, max_attempts=max_attempts)
    except Exception:
        logger.warning("generation_progress_callback_failed stage=%s", stage, exc_info=True)

COMPACT_OUTPUT_INSTRUCTION = (
    "\n\nИСПРАВЛЕНИЕ: предыдущий ответ исчерпал лимит выходных токенов и был обрезан.\n"
    "Сократи ответ значительно, сохранив все обязательные поля контракта:\n"
    "- верни ТОЛЬКО JSON, без markdown и без текста вне JSON;\n"
    "- шаги приготовления короткие, максимум 4-6 шагов на рецепт;\n"
    "- не повторяй очевидную информацию;\n"
    "- не добавляй необязательные поля;\n"
    "- используй короткие строковые значения;\n"
    "- description не длиннее одного предложения."
)

STRATEGY_MEAL_SCHEMA = (
    '{"type":"breakfast","recipe_name":"Название блюда","recipe_id":"recipe_day1_breakfast",'
    '"cooking_instance_id":"cook_day1_breakfast","meal_id":"day1_breakfast",'
    '"requires_cooking":true,"prepared_on_day":1,"uses_leftovers":false,"source_meal_id":null}'
)
LEGACY_MEAL_SCHEMA = '{"type":"breakfast","recipe_name":"Название блюда"}'
STRATEGY_RECIPE_SCHEMA = (
    '{{"recipe_id":"recipe_day1_breakfast","name":"Название","emoji":"🍲","cook_time":"30 мин",'
    '"difficulty":"Легко","calories_per_portion":"400 ккал","description":"Описание",'
    '"kbju":"Б:25г Ж:10г У:40г","ingredients":[{{"name":"Ингредиент","amount":"400г",'
    '"contribution":"purchase"}}],"steps":["Шаг 1","Шаг 2"]}}'
)

PROTEIN_NAMES = {
    "chicken": "курица", "beef": "говядина", "pork": "свинина",
    "fish": "рыба", "seafood": "морепродукты", "eggs": "яйца и молочные продукты",
    "veggie": "без мяса (овощи, бобовые, крупы)", "any": "любые продукты",
}

GOAL_NAMES = {
    "healthy": "🥗 Правильное питание", "home": "🏠 Домашняя еда",
    "muscle": "💪 Набор массы", "weightloss": "⚖️ Похудение",
    "restaurant": "🍽 Ресторан дома", "budget": "💰 Экономно",
}

COOKTIME_NAMES = {
    "fast": "до 20 минут", "medium": "до 45 минут", "slow": "до 90 минут",
}

GOAL_PROMPTS = {
    "healthy": "\nЦЕЛЬ — ПРАВИЛЬНОЕ ПИТАНИЕ:\n- Только цельные необработанные продукты\n- Способы готовки: варка, запекание, на пару, тушение\n- Много овощей и клетчатки\n- Для каждого рецепта укажи КБЖУ\n- Баланс: белок 25-30%, жиры 25-30%, углеводы 40-50%",
    "home": "\nЦЕЛЬ — ДОМАШНЯЯ ЕДА:\n- Классические домашние блюда которые любят все\n- Только простые доступные ингредиенты\n- Борщ, котлеты, пюре, супы, каши\n- Никакой экзотики, всё понятно и привычно\n- Сытно, вкусно, просто",
    "muscle": "\nЦЕЛЬ — НАБОР МЫШЕЧНОЙ МАССЫ:\n- Высокая калорийность, минимум 30-40г белка на приём\n- Мясо или рыба в каждом приёме пищи\n- Сложные углеводы во ВСЕХ приёмах включая ужин: рис, гречка, макароны\n- Углеводы на ужин разрешены\n- Для каждого рецепта укажи калории и белок на порцию",
    "weightloss": "\nЦЕЛЬ — ПОХУДЕНИЕ:\n- Дефицит калорий: 400-500 ккал/порция\n- Много белка для сытости: минимум 25г на порцию\n- УЖИН строго: только белок плюс овощи, без углеводов\n- Углеводы только на завтрак и обед\n- Для каждого рецепта укажи КБЖУ на порцию\n- Никакого сахара",
    "restaurant": "\nЦЕЛЬ — РЕСТОРАН ДОМА:\n- Используй РАЗНЫЕ кухни мира по дням\n- Профессиональные техники: карамелизация, деглазирование\n- Авторский соус к каждому блюду\n- Опиши подачу как в ресторане\n- Укажи рекомендацию напитка к каждому блюду",
    "budget": "\nЦЕЛЬ — ЭКОНОМНОЕ МЕНЮ:\n- Основной белок: курица бёдра, яйца, консервы\n- Бобовые: чечевица, нут, фасоль\n- Сезонные овощи: капуста, морковь, картофель\n- Никакой говядины, морепродуктов, экзотики",
}

BASE_SYSTEM = """Ты — персональный кулинарный планировщик для семей в России.
═══ ПРИНЦИП 1: МИНИМУМ ОСТАТКОВ ═══
Сначала выбери 4-6 ключевых продуктов, затем построй меню так, чтобы каждый продукт использовался ПОЛНОСТЬЮ.
═══ ПРИНЦИП 2: РАЗНООБРАЗИЕ ═══
Меняй способ готовки и тип блюда. Не повторяй одно блюдо чаще чем раз в 3 дня.
═══ ПРИНЦИП 3: ЛОГИКА ПРИЁМОВ ПИЩИ ═══
ЗАВТРАК — каши, омлеты, яичница, творог, сырники, тосты. Запрещено: супы, тяжёлое мясо.
ОБЕД — самый сытный: суп/борщ + второе или большое горячее.
УЖИН — лёгкий: рыба, курица, овощи, паста, котлеты. АБСОЛЮТНО ЗАПРЕЩЕНО: яичница, омлеты, блины, сырники, каши.
═══ ПРИНЦИП 5: БЮДЖЕТ ═══
Бюджет указан на весь период планирования. total_cost должен равняться сумме basket item.price.
ТРЕБОВАНИЯ К ОТВЕТУ:
- Цены реалистичные для РФ 2024-2025 года
- Верни ТОЛЬКО JSON без markdown, комментариев и пояснений
- Каждое блюдо в days_plan должно иметь рецепт с точно таким же названием
- Каждый рецепт должен использоваться в days_plan
- Ингредиенты рассчитаны на указанное количество человек
- Соблюдай запрещённые продукты и лимит времени готовки
- Не добавляй четвёртый приём пищи"""


def build_system_prompt(goal: str, strategy: WeeklyStrategy | None = None) -> str:
    system = BASE_SYSTEM + "\n" + GOAL_PROMPTS.get(goal, "")
    if strategy is not None:
        system += "\n" + build_strategy_system_section()
    return system


def build_operational_prompt(
    *,
    persons: int,
    store: str,
    days: int,
    meal_types: list[str],
) -> str:
    """Operational fields not covered by WeeklyStrategy."""
    total_meals = days * len(meal_types)
    meal_types_lines = "\n".join(
        f"  - {meal_type}: {MEAL_TYPE_LABELS_RU.get(meal_type, meal_type)}"
        for meal_type in meal_types
    )
    store_line = f"- Магазин (справочно): {store}" if store and store != "any" else ""

    recipe_schema = STRATEGY_RECIPE_SCHEMA
    meal_schema = STRATEGY_MEAL_SCHEMA
    day_schema = (
        f'{{"day":"День 1","meals":[{meal_schema}],"breakfast":"","lunch":"","dinner":""}}'
    )

    return f"""Составь план питания по WEEKLY_STRATEGY.
Операционные параметры (не стратегические):
- Человек: {persons}
- Блюд всего: {total_meals}
{store_line}
- Структура meals[] (ровно по одному каждого типа в день):
{meal_types_lines}

Верни JSON:
{{
  "summary": "1-2 предложения",
  "total_cost": 0,
  "days_plan": [{day_schema}],
  "recipes": [{recipe_schema}],
  "basket": [{{"category": "Категория", "items": [{{"name": "Продукт", "weight": "500 г", "price": 0}}]}}]
}}
Строго:
- days_plan ровно {days} элементов
- meals[] содержит только типы из WEEKLY_STRATEGY
- Каждый meal содержит meal_id, recipe_id, cooking_instance_id, requires_cooking, prepared_on_day, uses_leftovers
- cooking_instance_id идентифицирует одно фактическое приготовление; source и leftover используют одну instance
- независимое повторное приготовление того же recipe_id использует новую cooking_instance_id
- recipe_id уникален в пределах меню; meal.recipe_id ссылается на существующий recipe.recipe_id
- recipe_name — display text; recipe_id не строить из названия блюда
- Каждый ingredient содержит contribution: purchase | from_source | pantry
- purchase — купить; from_source — из ранее приготовленного (только при uses_leftovers=true)
- pantry — ТОЛЬКО если название ингредиента буквально: соль, вода, перец, масло, специи; именованные специи и добавки (паприка, кумин, зелень, мёд и т.п.) — purchase
- Leftover meal должен иметь хотя бы один from_source ingredient
- source_meal_id обязателен при uses_leftovers=true
- Новая готовка (requires_cooking=true) только в cook_days из WEEKLY_STRATEGY
- recipe_name в meals[] совпадает с recipe.name
- Каждый recipe используется в days_plan
- total_cost равен сумме basket item.price
- Ингредиенты рассчитаны на {persons} человек"""


def build_prompt(
    budget,
    days,
    meal_types: list[str],
    persons,
    proteins,
    goal,
    cooktime,
    allergies,
    strategy: WeeklyStrategy | None = None,
    store: str = "any",
):
    if strategy is not None:
        return (
            build_strategy_prompt_section(strategy)
            + "\n\n"
            + build_operational_prompt(
                persons=persons,
                store=store,
                days=days,
                meal_types=meal_types,
            )
        )

    total_meals = days * len(meal_types)
    protein_text = ", ".join(PROTEIN_NAMES.get(p, p) for p in proteins)
    cooktime_text = COOKTIME_NAMES.get(cooktime, "до 45 минут")
    goal_text = GOAL_NAMES.get(goal, "домашняя еда")
    allergy_line = f"- Исключить: {allergies}" if allergies and allergies != "нет" else ""
    meal_types_lines = "\n".join(
        f"  - {meal_type}: {MEAL_TYPE_LABELS_RU.get(meal_type, meal_type)}"
        for meal_type in meal_types
    )

    recipe_schema = '{{"name":"Название","emoji":"🍲","cook_time":"30 мин","difficulty":"Легко","calories_per_portion":"400 ккал","description":"Описание","kbju":"Б:25г Ж:10г У:40г","ingredients":[{{"name":"Ингредиент","amount":"400г"}}],"steps":["Шаг 1","Шаг 2"]}}'
    meal_schema = LEGACY_MEAL_SCHEMA
    day_schema = (
        f'{{"day":"День 1","meals":[{meal_schema}],"breakfast":"","lunch":"","dinner":""}}'
    )

    return f"""Составь план питания:
- Бюджет на весь период: {int(budget)} ₽
- Дней: {days}, блюд всего: {total_meals}
- Человек: {persons}
- Продукты: {protein_text}
{allergy_line}
- Цель: {goal_text}
- Время готовки: {cooktime_text}
- Приёмы пищи (создай только их, каждый день ровно по одному каждого типа):
{meal_types_lines}

Верни JSON:
{{
  "summary": "1-2 предложения",
  "total_cost": 0,
  "days_plan": [{day_schema}],
  "recipes": [{recipe_schema}],
  "basket": [{{"category": "Категория", "items": [{{"name": "Продукт", "weight": "500 г", "price": 0}}]}}]
}}
Строго:
- days_plan ровно {days} элементов
- В каждом дне meals[] содержит только выбранные типы: {", ".join(meal_types)}
- Не добавляй невыбранные типы приёмов пищи
- breakfast — блюдо для завтрака; lunch — полноценный обед; dinner — ужин; snack — простой перекус
- Не заменяй типы местами
- recipe_name в meals[] совпадает с recipe.name
- Каждый recipe используется в days_plan
- total_cost равен сумме basket item.price
- Ингредиенты рассчитаны на {persons} человек
- Не превышай бюджет {int(budget)} ₽ на весь период"""


def _issue_detail(issue) -> str:
    """Correction-prompt detail: message plus path so the model can locate the violation."""
    if issue.path:
        return f"{issue.message} (path: {issue.path})"
    return issue.message


def _issue_payload(issue) -> dict[str, object]:
    """Structured issue for targeted correction prompts and diagnostics."""
    return {
        "code": issue.code,
        "message": _issue_detail(issue),
        "path": issue.path,
        "meta": getattr(issue, "meta", None),
    }


def _menu_stats(
    menu_plan: MenuPlan,
    *,
    shopping_cost: float | None = None,
    budget_limit: float | None = None,
) -> dict[str, object]:
    """Quality metrics of a plan, used for retry regression detection."""
    unique_recipes = {recipe.recipe_id or recipe.name.strip().lower() for recipe in menu_plan.recipes}
    stats: dict[str, object] = {
        "unique_recipe_count": len(unique_recipes),
        "meal_count": sum(len(day.meals) for day in menu_plan.days_plan),
    }
    if shopping_cost is not None:
        stats["shopping_cost"] = float(shopping_cost)
    if budget_limit is not None:
        stats["budget_limit"] = float(budget_limit)
    return stats


def _raise_menu_constraint(
    message: str,
    errors: list,
    menu_plan: MenuPlan,
    *,
    shopping_cost: float | None = None,
    budget_limit: float | None = None,
) -> None:
    """Raise MenuConstraintError with structured issues, stats, and meal inventory."""
    raise MenuConstraintError(
        message,
        issue_codes=[issue.code for issue in errors],
        issue_messages=[_issue_detail(issue) for issue in errors],
        issues=[_issue_payload(issue) for issue in errors],
        menu_stats=_menu_stats(
            menu_plan,
            shopping_cost=shopping_cost,
            budget_limit=budget_limit,
        ),
        meal_inventory=build_meal_usage_inventory(menu_plan),
    )


def _constraint_metrics(exc: MenuConstraintError) -> dict[str, object]:
    """Comparable metrics of a failed constraint attempt."""
    by_code: dict[str, int] = {}
    for code in exc.issue_codes:
        by_code[code] = by_code.get(code, 0) + 1
    unique = exc.menu_stats.get("unique_recipe_count")
    unique_count = unique if isinstance(unique, int) else 0
    return {
        "total_issue_count": len(exc.issue_codes),
        "duplicate_issue_count": by_code.get("MEAL_DUPLICATE_EXCESSIVE", 0),
        "cooktime_issue_count": by_code.get("COOKTIME_EXCEEDED", 0),
        "issue_count_by_code": by_code,
        "unique_recipe_count": unique if isinstance(unique, int) else None,
        "score": _candidate_score(
            issue_count=len(exc.issue_codes),
            unique_recipe_count=unique_count,
            cooktime_issue_count=by_code.get("COOKTIME_EXCEEDED", 0),
        ),
    }


def _candidate_score(
    *,
    issue_count: int,
    unique_recipe_count: int,
    cooktime_issue_count: int,
) -> int:
    """Higher is better. Prefer fewer issues over raw variety."""
    return 100 - 20 * issue_count + unique_recipe_count - cooktime_issue_count


def _detect_correction_regression(
    previous: dict[str, object],
    current: dict[str, object],
) -> list[str]:
    """Reasons why the retry is worse than the previous attempt (empty = no regression)."""
    reasons: list[str] = []
    if current["total_issue_count"] > previous["total_issue_count"]:
        reasons.append("issue_count_increased")
    prev_unique = previous.get("unique_recipe_count")
    cur_unique = current.get("unique_recipe_count")
    if isinstance(prev_unique, int) and isinstance(cur_unique, int) and cur_unique < prev_unique:
        reasons.append("unique_recipe_count_decreased")
    new_codes = set(current["issue_count_by_code"]) - set(previous["issue_count_by_code"])
    if new_codes:
        reasons.append(f"new_issue_types={sorted(new_codes)}")
    prev_score = previous.get("score")
    cur_score = current.get("score")
    if isinstance(prev_score, int) and isinstance(cur_score, int) and cur_score < prev_score:
        reasons.append("score_decreased")
    return reasons


def _structured_issues_from_exc(exc: MenuConstraintError) -> list[dict[str, object]]:
    correction_messages = (
        exc.issue_messages
        if len(exc.issue_messages) == len(exc.issue_codes)
        else [f"Menu constraint: {code}" for code in exc.issue_codes]
    )
    if len(exc.issues) == len(exc.issue_codes):
        return list(exc.issues)
    return [
        {"code": code, "message": message, "meta": None}
        for code, message in zip(exc.issue_codes, correction_messages)
    ]


def _log_validation_failure(
    request_id: str,
    user_id: Optional[int],
    days: int,
    persons: int,
    result_errors: list,
    duration_ms: int,
) -> None:
    issue_codes = [issue.code for issue in result_errors]
    paths = [issue.path for issue in result_errors if issue.path]
    reason_codes = [issue.reason_code for issue in result_errors if getattr(issue, "reason_code", None)]
    logger.warning(
        "generation_failed event=validation_failed request_id=%s user_id=%s days=%s persons=%s "
        "issue_codes=%s issue_count=%s reason_codes=%s paths=%s duration_ms=%s",
        request_id,
        user_id,
        days,
        persons,
        issue_codes,
        len(issue_codes),
        reason_codes,
        paths[:10],
        duration_ms,
    )
    # Structured per-issue diagnostics (duplicate positions, cooktime details).
    for issue in result_errors:
        meta = getattr(issue, "meta", None)
        if meta:
            logger.warning(
                "constraint_issue_detail request_id=%s code=%s path=%s meta=%s",
                request_id,
                issue.code,
                issue.path,
                meta,
            )


def process_claude_response(
    raw_text: str,
    request: MenuValidationRequest,
    request_id: str,
    user_id: Optional[int],
    started_at: float,
    strategy: WeeklyStrategy | None = None,
    plan_start_date: date | None = None,
    *,
    stop_reason: str | None = None,
    attempt: int | None = None,
    reliability: GenerationReliabilityStats | None = None,
) -> dict[str, object]:
    logger.info(
        "menu_parse_started request_id=%s raw_chars=%s",
        request_id,
        len(raw_text),
    )
    try:
        extract_result = extract_json_object_with_meta(
            raw_text,
            stop_reason=stop_reason,
        )
    except ClaudeJsonError as exc:
        diag = getattr(exc, "diagnostics", None)
        if diag is not None and getattr(diag, "recovery_attempted", False):
            logger.warning(
                "json_recovery_attempted request_id=%s attempt=%s raw_chars=%s",
                request_id,
                attempt,
                len(raw_text),
            )
            logger.warning(
                "json_recovery_failed request_id=%s attempt=%s "
                "json_error_type=%s json_error_position=%s json_error_message=%s "
                "stop_reason=%s raw_chars=%s",
                request_id,
                attempt,
                getattr(diag, "json_error_type", None),
                getattr(diag, "json_error_position", None),
                getattr(diag, "json_error_message", None),
                stop_reason,
                len(raw_text),
            )
            if reliability is not None:
                reliability.json_recovery_failures += 1
        logger.exception(
            "menu_parse_failed request_id=%s raw_chars=%s raw_tail=%r "
            "json_error_type=%s json_error_position=%s stop_reason=%s",
            request_id,
            len(raw_text),
            raw_text[-200:] if raw_text else "",
            getattr(diag, "json_error_type", None) if diag is not None else None,
            getattr(diag, "json_error_position", None) if diag is not None else None,
            stop_reason,
        )
        raise

    if extract_result.diagnostics.recovery_attempted:
        logger.info(
            "json_recovery_attempted request_id=%s attempt=%s raw_chars=%s",
            request_id,
            attempt,
            len(raw_text),
        )
    if extract_result.recovered:
        logger.info(
            "json_recovery_succeeded request_id=%s attempt=%s recovery_mode=%s",
            request_id,
            attempt,
            extract_result.diagnostics.recovery_mode,
        )
        if reliability is not None:
            reliability.local_json_recoveries += 1

    payload = extract_result.payload
    # plan_start_date and strategy_id are assigned by the application, not by Claude.
    payload.pop("plan_start_date", None)
    payload.pop("strategy_id", None)
    if isinstance(payload.get("days_plan"), list):
        payload["days_plan"] = normalize_days_plan_payload(
            payload["days_plan"],
            request.meal_types,
        )
    logger.info("menu_parse_completed request_id=%s recovered=%s", request_id, extract_result.recovered)

    logger.info("validation_started request_id=%s", request_id)
    try:
        menu_plan = MenuPlan.model_validate(payload)
    except ValidationError as exc:
        details = [
            f"{'.'.join(str(part) for part in err.get('loc', ()))}: {err.get('msg', 'invalid')}"
            for err in exc.errors()[:12]
        ]
        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.exception(
            "generation_failed event=schema_validation_failed request_id=%s user_id=%s "
            "error_count=%s details=%s duration_ms=%s",
            request_id,
            user_id,
            len(exc.errors()),
            details,
            duration_ms,
        )
        raise ClaudeValidationError(
            "Menu schema validation failed",
            details=details,
        ) from exc

    strategy_aware = strategy is not None
    menu_plan, id_issues = assign_and_validate_recipe_ids(
        menu_plan,
        strategy_aware=strategy_aware,
    )
    id_errors = [issue for issue in id_issues if issue.severity == "error"]
    if id_errors:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        _log_validation_failure(
            request_id,
            user_id,
            request.days,
            request.persons,
            id_errors,
            duration_ms,
        )
        _raise_menu_constraint(
            "Recipe identity validation failed",
            id_errors,
            menu_plan,
        )

    # Sprint 10.7: deterministic cooking/leftover relational normalization
    # before strict cooking / contribution validators.
    menu_plan, meta_stats = normalize_cooking_leftover_metadata(
        menu_plan,
        request_id=request_id,
    )
    norm_count = (
        meta_stats.cooking_normalized + meta_stats.leftover_normalized
    )
    if reliability is not None and norm_count:
        reliability.metadata_normalizations += norm_count

    menu_plan, cooking_issues = assign_and_validate_cooking_instances(
        menu_plan,
        strategy_aware=strategy_aware,
    )
    cooking_errors = [issue for issue in cooking_issues if issue.severity == "error"]
    if cooking_errors:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        _log_validation_failure(
            request_id,
            user_id,
            request.days,
            request.persons,
            cooking_errors,
            duration_ms,
        )
        _raise_menu_constraint(
            "Cooking instance validation failed",
            cooking_errors,
            menu_plan,
        )

    # total_cost is a derived field: the backend owns the arithmetic. Claude's
    # own addition is replaced by the canonical basket sum before constraint
    # validation, so arithmetic-only mismatches never reach the correction loop.
    # Individual item prices are never modified.
    menu_plan, cost_normalization = normalize_total_cost(menu_plan)
    model_total_diag = cost_normalization.model_total
    calculated_total_diag = cost_normalization.calculated_total
    if cost_normalization.normalized:
        logger.info(
            "total_cost_normalized request_id=%s model_total=%s calculated_total=%s difference=%s",
            request_id,
            cost_normalization.model_total,
            cost_normalization.calculated_total,
            cost_normalization.difference,
        )
    elif cost_normalization.reason == "invalid_price_contributions":
        # Bad price data must surface as a validation error, not be masked.
        logger.warning(
            "total_cost_not_normalized request_id=%s reason=%s model_total=%s",
            request_id,
            cost_normalization.reason,
            cost_normalization.model_total,
        )

    validation = validate_menu_plan(
        menu_plan,
        replace(request, strategy_aware=strategy_aware),
        # Sprint 10.8: user weekly budget is enforced only after BasketEngine
        # rebuild using shopping_cost — not Claude model_total / recipe basket.
        enforce_user_budget=strategy is None,
    )
    if not validation.is_valid:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        _log_validation_failure(
            request_id,
            user_id,
            request.days,
            request.persons,
            validation.errors,
            duration_ms,
        )
        _raise_menu_constraint(
            "Menu constraint validation failed",
            validation.errors,
            menu_plan,
        )

    if strategy is not None:
        try:
            validate_menu_against_strategy(menu_plan, strategy)
        except StrategyComplianceError as exc:
            duration_ms = int((time.monotonic() - started_at) * 1000)
            logger.warning(
                "generation_failed event=strategy_compliance_failed request_id=%s user_id=%s "
                "issue_codes=%s issue_count=%s duration_ms=%s",
                request_id,
                user_id,
                exc.issue_codes,
                len(exc.issue_codes),
                duration_ms,
            )
            raise

    if validation.warnings and config.ENVIRONMENT != "production":
        logger.info(
            "generation_completed warnings request_id=%s warning_codes=%s warning_count=%s",
            request_id,
            [issue.code for issue in validation.warnings],
            len(validation.warnings),
        )
    logger.info("validation_completed request_id=%s", request_id)

    if plan_start_date is not None:
        menu_plan = menu_plan.model_copy(update={"plan_start_date": plan_start_date})

    if strategy is not None:
        logger.info("basket_build_started request_id=%s", request_id)
        claude_basket_count = sum(len(category.items) for category in menu_plan.basket)
        claude_total = menu_plan.total_cost
        try:
            rebuild = build_basket_from_menu(menu_plan, existing_basket=menu_plan.basket)
        except Exception:
            logger.exception("basket_build_failed request_id=%s", request_id)
            raise
        menu_plan = menu_plan.model_copy(
            update={
                "basket": rebuild.basket,
                "total_cost": float(rebuild.total_cost or 0),
            }
        )
        if config.ENVIRONMENT != "production":
            rebuilt_count = sum(len(category.items) for category in menu_plan.basket)
            logger.info(
                "basket_rebuild_shadow request_id=%s claude_items=%s rebuilt_items=%s "
                "claude_total=%s rebuilt_total=%s unresolved_prices=%s",
                request_id,
                claude_basket_count,
                rebuilt_count,
                claude_total,
                menu_plan.total_cost,
                len(rebuild.unresolved_prices),
            )
        logger.info("basket_build_completed request_id=%s", request_id)

        # Authoritative weekly budget gate (shopping_cost after BasketEngine).
        shopping_cost = float(menu_plan.total_cost)
        budget_errors = validate_shopping_budget(
            shopping_cost,
            float(request.budget),
        )
        if budget_errors:
            duration_ms = int((time.monotonic() - started_at) * 1000)
            _log_validation_failure(
                request_id,
                user_id,
                request.days,
                request.persons,
                budget_errors,
                duration_ms,
            )
            _raise_menu_constraint(
                "Shopping budget validation failed",
                budget_errors,
                menu_plan,
                shopping_cost=shopping_cost,
                budget_limit=float(request.budget),
            )

    payload = menu_plan.model_dump(mode="json")
    # Diagnostic only — not authoritative for weekly budget.
    if model_total_diag is not None:
        payload["model_total"] = float(model_total_diag)
    if calculated_total_diag is not None:
        payload["calculated_total"] = float(calculated_total_diag)

    if strategy is not None:
        utilization = compute_budget_utilization(menu_plan, float(strategy.budget))
        if utilization is not None:
            payload.update(utilization.as_wire_fields())
            recipe_vs_basket = round(
                utilization.shopping_cost - utilization.recipe_cost, 2
            )
            model_vs_recipe = None
            if model_total_diag is not None and utilization.recipe_cost is not None:
                model_vs_recipe = round(
                    float(model_total_diag) - float(utilization.recipe_cost), 2
                )
            model_vs_basket = None
            if model_total_diag is not None:
                model_vs_basket = round(
                    float(model_total_diag) - float(utilization.shopping_cost), 2
                )
            logger.info(
                "budget_utilization request_id=%s budget_limit=%s recipe_cost=%s "
                "shopping_cost=%s budget_usage_percent=%s in_target=%s underutilized=%s "
                "model_total=%s calculated_total=%s model_vs_recipe_difference=%s "
                "recipe_vs_basket_difference=%s model_vs_basket_difference=%s",
                request_id,
                utilization.budget_limit,
                utilization.recipe_cost,
                utilization.shopping_cost,
                utilization.budget_usage_percent,
                utilization.in_target_range,
                utilization.underutilized,
                model_total_diag,
                calculated_total_diag,
                model_vs_recipe,
                recipe_vs_basket,
                model_vs_basket,
            )
            # Diagnostic: Claude self-estimate vs authoritative shopping cost.
            # Threshold: ≥15% of budget_limit or ≥500 ₽ absolute (documented).
            if model_total_diag is not None and utilization.budget_limit > 0:
                abs_diff = abs(float(model_total_diag) - float(utilization.shopping_cost))
                pct_of_budget = abs_diff / float(utilization.budget_limit)
                if abs_diff >= 500.0 or pct_of_budget >= 0.15:
                    logger.warning(
                        "cost_model_discrepancy request_id=%s model_total=%s "
                        "recipe_cost=%s shopping_cost=%s budget_limit=%s "
                        "model_vs_basket_difference=%s pct_of_budget=%s",
                        request_id,
                        model_total_diag,
                        utilization.recipe_cost,
                        utilization.shopping_cost,
                        utilization.budget_limit,
                        model_vs_basket,
                        round(pct_of_budget, 3),
                    )

    return payload


async def generate_menu(
    budget: float,
    days: int,
    meal_types: list[str],
    meals_per_day: int,
    persons: int,
    proteins: list,
    goal: str,
    cooktime: str,
    allergies: str,
    store: str = "any",
    user_id: Optional[int] = None,
    strategy: WeeklyStrategy | None = None,
    plan_start_date: date | None = None,
    progress_callback: GenerationProgressCallback | None = None,
) -> dict[str, object]:
    request_id = str(uuid.uuid4())
    started_at = time.monotonic()
    resolved_plan_start_date = plan_start_date or date.today()
    reliability = GenerationReliabilityStats()

    def _log_reliability(final_result: str) -> None:
        logger.info(
            "generation_reliability_summary request_id=%s final_result=%s "
            "llm_attempts=%s local_json_recoveries=%s metadata_normalizations=%s "
            "correction_count=%s json_recovery_failures=%s",
            request_id,
            final_result,
            reliability.llm_attempts,
            reliability.local_json_recoveries,
            reliability.metadata_normalizations,
            reliability.correction_count,
            reliability.json_recovery_failures,
        )

    def _succeed(payload: dict[str, object]) -> dict[str, object]:
        _log_reliability("succeeded")
        return payload

    if strategy is not None:
        budget = strategy.budget
        days = strategy.days
        meal_types = list(strategy.meal_types)
        meals_per_day = strategy.meals_per_day
        goal = strategy.goal
        proteins = list(strategy.preferred_proteins)

    validation_request = MenuValidationRequest(
        days=days,
        budget=budget,
        meal_types=meal_types,
        meals_per_day=meals_per_day,
        persons=persons,
        cooktime=cooktime,
        allergies=allergies,
    )

    logger.info(
        "generation_started request_id=%s user_id=%s days=%s persons=%s strategy_version=%s",
        request_id,
        user_id,
        days,
        persons,
        strategy.strategy_version if strategy else None,
    )
    await _emit_generation_progress(
        progress_callback,
        stage="generating",
        attempt=1,
        max_attempts=MAX_LLM_ATTEMPTS,
    )

    if strategy is not None:
        logger.info(
            "strategy_prompt request_id=%s strategy_version=%s meal_types=%s "
            "cook_days=%s shopping_days=%s cooking_time_limit=%s compliance_enabled=true",
            request_id,
            strategy.strategy_version,
            strategy.meal_types,
            strategy.cook_days,
            strategy.shopping_days,
            strategy.cooking_time_limit,
        )

    system = build_system_prompt(goal, strategy=strategy)
    base_prompt = build_prompt(
        budget,
        days,
        meal_types,
        persons,
        proteins,
        goal,
        cooktime,
        allergies,
        strategy=strategy,
        store=store,
    )
    correction_suffix = ""
    compact_mode = False
    # Best failed candidate (by score). A regressing retry is logged and discarded
    # as the correction base — the next attempt continues from the best, not the worse.
    best_candidate: dict[str, object] | None = None
    budget_optimizer_active = False
    budget_optimizer_corrections = 0
    budget_optimizer_baseline: dict[str, object] | None = None
    budget_optimizer_best: dict[str, object] | None = None
    budget_optimizer_target = None
    budget_optimizer_feedback: str | None = None
    budget_optimizer_last_shopping: float | None = None

    # Deterministic size estimate: helps correlate truncation with request scale.
    logger.info(
        "generation_output_budget request_id=%s days=%s meal_count=%s persons=%s "
        "meal_types=%s max_tokens=%s prompt_chars=%s system_chars=%s compact_mode=false",
        request_id,
        days,
        days * meals_per_day,
        persons,
        meal_types,
        config.CLAUDE_MAX_TOKENS,
        len(base_prompt),
        len(system),
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
        if attempt > 1:
            if budget_optimizer_active:
                await _emit_generation_progress(
                    progress_callback,
                    stage="optimizing_budget",
                    attempt=attempt,
                    max_attempts=MAX_LLM_ATTEMPTS,
                )
            else:
                await _emit_generation_progress(
                    progress_callback,
                    stage="correcting",
                    attempt=attempt,
                    max_attempts=MAX_LLM_ATTEMPTS,
                )
        prompt = base_prompt + correction_suffix
        request_body: dict[str, object] = {
            "model": config.CLAUDE_MODEL,
            "max_tokens": config.CLAUDE_MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        # Strict JSON generation never needs extended thinking; reasoning tokens
        # count against max_tokens and can starve the final text block.
        if config.CLAUDE_DISABLE_THINKING:
            request_body["thinking"] = {"type": "disabled"}
        try:
            async with create_anthropic_client() as client:
                reliability.llm_attempts += 1
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": config.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=request_body,
                )

            if is_retryable_anthropic_status(response.status_code):
                provider_error = parse_anthropic_error(response)
                if attempt >= MAX_LLM_ATTEMPTS:
                    logger.error(
                        "generation_failed request_id=%s status=%s "
                        "configured_model=%s "
                        "provider_error_type=%s provider_message=%s "
                        "provider_request_id=%s duration_ms=%s",
                        request_id,
                        response.status_code,
                        config.CLAUDE_MODEL,
                        provider_error.error_type,
                        provider_error.error_message,
                        provider_error.anthropic_request_id,
                        int((time.monotonic() - started_at) * 1000),
                    )
                    raise ClaudeUnavailableError("Claude API returned non-200 status")

                delay_seconds = compute_retry_delay_seconds(attempt, response)
                logger.warning(
                    "anthropic_retry request_id=%s attempt=%s max_attempts=%s "
                    "status=%s provider_error_type=%s delay_seconds=%s",
                    request_id,
                    attempt,
                    MAX_LLM_ATTEMPTS,
                    response.status_code,
                    provider_error.error_type,
                    delay_seconds,
                )
                await asyncio.sleep(delay_seconds)
                continue

            if response.status_code != 200:
                provider_error = parse_anthropic_error(response)
                logger.error(
                    "generation_failed request_id=%s status=%s "
                    "configured_model=%s "
                    "provider_error_type=%s provider_message=%s "
                    "provider_request_id=%s duration_ms=%s",
                    request_id,
                    response.status_code,
                    config.CLAUDE_MODEL,
                    provider_error.error_type,
                    provider_error.error_message,
                    provider_error.anthropic_request_id,
                    int((time.monotonic() - started_at) * 1000),
                )
                raise ClaudeUnavailableError("Claude API returned non-200 status")

            try:
                data = response.json()
            except Exception:
                logger.exception(
                    "claude_response_body_unreadable request_id=%s status=%s "
                    "content_length=%s",
                    request_id,
                    response.status_code,
                    len(response.content or b""),
                )
                raise ClaudeUnavailableError("Claude response body is not JSON")
            raw = "".join(
                block["text"]
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
            stop_reason = data.get("stop_reason")
            usage = data.get("usage") or {}
            output_tokens = usage.get("output_tokens")
            logger.info(
                "claude_response_received request_id=%s attempt=%s stop_reason=%s "
                "raw_chars=%s output_tokens=%s",
                request_id,
                attempt,
                stop_reason,
                len(raw),
                output_tokens,
            )

            # Fail-fast: max_tokens with no usable text is truncation, not a
            # JSON parse problem. Never feed it to the parser.
            if stop_reason == "max_tokens" and not raw.strip():
                logger.warning(
                    "generation_failed event=output_truncated request_id=%s attempt=%s "
                    "stop_reason=%s output_tokens=%s raw_chars=%s",
                    request_id,
                    attempt,
                    stop_reason,
                    output_tokens,
                    len(raw),
                )
                if attempt >= MAX_LLM_ATTEMPTS:
                    raise ClaudeOutputTruncatedError(
                        "Claude exhausted max_tokens without a usable text block",
                        stop_reason=stop_reason,
                        output_tokens=output_tokens,
                        raw_chars=len(raw),
                    )
                compact_mode = True
                correction_suffix = COMPACT_OUTPUT_INSTRUCTION
                logger.warning(
                    "generation_retry request_id=%s event=output_truncated attempt=%s "
                    "retry_mode=compact_output",
                    request_id,
                    attempt,
                )
                logger.info(
                    "generation_output_budget request_id=%s days=%s meal_count=%s persons=%s "
                    "meal_types=%s max_tokens=%s prompt_chars=%s system_chars=%s compact_mode=true",
                    request_id,
                    days,
                    days * meals_per_day,
                    persons,
                    meal_types,
                    config.CLAUDE_MAX_TOKENS,
                    len(base_prompt + correction_suffix),
                    len(system),
                )
                continue

            try:
                result = process_claude_response(
                    raw,
                    validation_request,
                    request_id,
                    user_id,
                    started_at,
                    strategy=strategy,
                    plan_start_date=resolved_plan_start_date,
                    stop_reason=stop_reason if isinstance(stop_reason, str) else None,
                    attempt=attempt,
                    reliability=reliability,
                )
            except StrategyComplianceError as exc:
                if budget_optimizer_active and budget_optimizer_baseline is not None:
                    if (
                        budget_optimizer_corrections < MAX_BUDGET_OPTIMIZER_CORRECTIONS
                        and attempt < MAX_LLM_ATTEMPTS
                        and strategy is not None
                        and budget_optimizer_target is not None
                    ):
                        logger.info(
                            "budget_optimizer_rejected request_id=%s reason=strategy_compliance "
                            "optimizer_attempt=%s issue_codes=%s",
                            request_id,
                            budget_optimizer_corrections,
                            exc.issue_codes,
                        )
                        budget_optimizer_feedback = build_budget_optimizer_feedback(
                            budget_limit=float(strategy.budget),
                            previous_shopping_cost=budget_optimizer_last_shopping,
                            issue_codes=list(exc.issue_codes),
                            reason="strategy_compliance",
                        )
                        budget_optimizer_corrections += 1
                        logger.info(
                            "budget_optimizer_attempt request_id=%s optimizer_attempt=%s "
                            "previous_shopping_cost=%s desired_delta=%s",
                            request_id,
                            budget_optimizer_corrections,
                            budget_optimizer_target.current_cost,
                            budget_optimizer_target.desired_delta,
                        )
                        correction_suffix = build_budget_optimizer_prompt(
                            budget_limit=float(strategy.budget),
                            shopping_cost=budget_optimizer_target.current_cost,
                            target=budget_optimizer_target,
                            feedback=budget_optimizer_feedback,
                        )
                        continue
                    logger.info(
                        "budget_optimizer_completed request_id=%s accepted=False "
                        "attempts=%s reason=strategy_compliance "
                        "initial_shopping_cost=%s final_shopping_cost=%s "
                        "initial_usage_percent=%s final_usage_percent=%s",
                        request_id,
                        budget_optimizer_corrections,
                        budget_optimizer_baseline.get("shopping_cost"),
                        (
                            budget_optimizer_best or budget_optimizer_baseline
                        ).get("shopping_cost"),
                        budget_optimizer_baseline.get("budget_usage_percent"),
                        (
                            budget_optimizer_best or budget_optimizer_baseline
                        ).get("budget_usage_percent"),
                    )
                    return _succeed(budget_optimizer_best or budget_optimizer_baseline)
                if strategy is None or attempt >= MAX_LLM_ATTEMPTS:
                    raise MenuConstraintError(
                        "Strategy compliance validation failed",
                        issue_codes=exc.issue_codes,
                    ) from exc
                logger.warning(
                    "generation_retry request_id=%s event=strategy_compliance attempt=%s issue_codes=%s",
                    request_id,
                    attempt,
                    exc.issue_codes,
                )
                reliability.correction_count += 1
                logger.info(
                    "generation_correction_attempt request_id=%s attempt=%s "
                    "reason_codes=%s targeted=%s",
                    request_id,
                    attempt,
                    exc.issue_codes,
                    False,
                )
                correction_suffix = (
                    "\n\n"
                    + build_correction_prompt(exc.issue_codes, exc.messages, strategy)
                )
                continue
            except MenuConstraintError as exc:
                if budget_optimizer_active and budget_optimizer_baseline is not None:
                    candidate_shopping = exc.menu_stats.get("shopping_cost")
                    if not isinstance(candidate_shopping, (int, float)):
                        candidate_shopping = None
                    budget_limit_val = float(strategy.budget) if strategy is not None else None
                    if (
                        candidate_shopping is not None
                        and budget_limit_val is not None
                    ):
                        overshoot = max(
                            0.0,
                            float(candidate_shopping) - float(budget_limit_val),
                        )
                        budget_optimizer_last_shopping = float(candidate_shopping)
                        usage_for_log = usage_percent_from_shopping(
                            float(candidate_shopping),
                            float(budget_limit_val),
                        )
                        logger.info(
                            "budget_optimizer_candidate request_id=%s optimizer_attempt=%s "
                            "model_total=%s recipe_cost=%s shopping_cost=%s "
                            "usage_percent=%s valid=%s issue_codes=%s",
                            request_id,
                            budget_optimizer_corrections,
                            None,
                            None,
                            candidate_shopping,
                            usage_for_log,
                            False,
                            list(exc.issue_codes or []),
                        )
                        logger.info(
                            "budget_optimizer_rejected request_id=%s reason=menu_constraint "
                            "optimizer_attempt=%s issue_codes=%s "
                            "authoritative_budget_cost=%s budget_limit=%s overshoot_amount=%s",
                            request_id,
                            budget_optimizer_corrections,
                            exc.issue_codes,
                            candidate_shopping,
                            budget_limit_val,
                            overshoot,
                        )
                    else:
                        overshoot = None
                        if (
                            strategy is not None
                            and budget_optimizer_last_shopping is not None
                        ):
                            overshoot = max(
                                0.0,
                                float(budget_optimizer_last_shopping)
                                - float(strategy.budget),
                            )
                        logger.info(
                            "budget_optimizer_rejected request_id=%s reason=menu_constraint "
                            "optimizer_attempt=%s issue_codes=%s overshoot_amount=%s",
                            request_id,
                            budget_optimizer_corrections,
                            exc.issue_codes,
                            overshoot,
                        )
                    if (
                        budget_optimizer_corrections < MAX_BUDGET_OPTIMIZER_CORRECTIONS
                        and attempt < MAX_LLM_ATTEMPTS
                        and strategy is not None
                        and budget_optimizer_target is not None
                    ):
                        budget_optimizer_feedback = build_budget_optimizer_feedback(
                            budget_limit=float(strategy.budget),
                            previous_shopping_cost=(
                                float(candidate_shopping)
                                if candidate_shopping is not None
                                else budget_optimizer_last_shopping
                            ),
                            issue_codes=list(exc.issue_codes or []),
                            overshoot_amount=overshoot,
                            reason="menu_constraint",
                        )
                        budget_optimizer_corrections += 1
                        logger.info(
                            "budget_optimizer_attempt request_id=%s optimizer_attempt=%s "
                            "previous_shopping_cost=%s desired_delta=%s",
                            request_id,
                            budget_optimizer_corrections,
                            budget_optimizer_target.current_cost,
                            budget_optimizer_target.desired_delta,
                        )
                        correction_suffix = build_budget_optimizer_prompt(
                            budget_limit=float(strategy.budget),
                            shopping_cost=budget_optimizer_target.current_cost,
                            target=budget_optimizer_target,
                            feedback=budget_optimizer_feedback,
                            previous_model_total=None,
                        )
                        continue
                    logger.info(
                        "budget_optimizer_completed request_id=%s accepted=False "
                        "attempts=%s reason=menu_constraint "
                        "initial_shopping_cost=%s final_shopping_cost=%s "
                        "initial_usage_percent=%s final_usage_percent=%s",
                        request_id,
                        budget_optimizer_corrections,
                        budget_optimizer_baseline.get("shopping_cost"),
                        (
                            budget_optimizer_best or budget_optimizer_baseline
                        ).get("shopping_cost"),
                        budget_optimizer_baseline.get("budget_usage_percent"),
                        (
                            budget_optimizer_best or budget_optimizer_baseline
                        ).get("budget_usage_percent"),
                    )
                    return _succeed(budget_optimizer_best or budget_optimizer_baseline)
                current_metrics = _constraint_metrics(exc)
                continue_from_best = False
                if best_candidate is not None:
                    best_metrics = best_candidate["metrics"]
                    assert isinstance(best_metrics, dict)
                    regression_reasons = _detect_correction_regression(
                        best_metrics,
                        current_metrics,
                    )
                    if regression_reasons:
                        # Worse than the best so far: keep best as the correction base.
                        continue_from_best = True
                        logger.warning(
                            "correction_regression_detected request_id=%s attempt=%s reasons=%s "
                            "best_issue_count=%s current_issue_count=%s "
                            "best_unique_recipe_count=%s current_unique_recipe_count=%s "
                            "best_score=%s current_score=%s",
                            request_id,
                            attempt,
                            regression_reasons,
                            best_metrics["total_issue_count"],
                            current_metrics["total_issue_count"],
                            best_metrics.get("unique_recipe_count"),
                            current_metrics.get("unique_recipe_count"),
                            best_metrics.get("score"),
                            current_metrics.get("score"),
                        )
                    else:
                        # Improved or equal on regression axes — accept as new best.
                        best_candidate = {
                            "metrics": current_metrics,
                            "issues": _structured_issues_from_exc(exc),
                            "meal_inventory": exc.meal_inventory,
                            "attempt": attempt,
                        }
                else:
                    best_candidate = {
                        "metrics": current_metrics,
                        "issues": _structured_issues_from_exc(exc),
                        "meal_inventory": exc.meal_inventory,
                        "attempt": attempt,
                    }

                if strategy is None or attempt >= MAX_LLM_ATTEMPTS:
                    raise

                # Correction base: best candidate when current regressed; else current.
                assert best_candidate is not None
                base_issues = best_candidate["issues"]
                base_inventory = best_candidate["meal_inventory"]
                base_metrics = best_candidate["metrics"]
                assert isinstance(base_issues, list)
                assert isinstance(base_metrics, dict)

                # Attempt 2 → targeted; final attempt → strict targeted.
                strict_mode = attempt + 1 >= MAX_LLM_ATTEMPTS
                logger.warning(
                    "generation_retry request_id=%s event=menu_constraint attempt=%s "
                    "retry_mode=targeted_constraint strict=%s continue_from_best=%s "
                    "issue_codes=%s issue_count_by_code=%s "
                    "best_issue_count=%s best_unique_recipe_count=%s best_score=%s",
                    request_id,
                    attempt,
                    strict_mode,
                    continue_from_best,
                    [issue.get("code") for issue in base_issues]
                    if continue_from_best
                    else exc.issue_codes,
                    base_metrics["issue_count_by_code"]
                    if continue_from_best
                    else current_metrics["issue_count_by_code"],
                    base_metrics["total_issue_count"],
                    base_metrics.get("unique_recipe_count"),
                    base_metrics.get("score"),
                )
                reliability.correction_count += 1
                issue_codes_for_log = (
                    [issue.get("code") for issue in base_issues]
                    if continue_from_best
                    else list(exc.issue_codes)
                )
                logger.info(
                    "generation_correction_attempt request_id=%s attempt=%s "
                    "reason_codes=%s targeted=%s",
                    request_id,
                    attempt,
                    issue_codes_for_log,
                    True,
                )
                correction_suffix = (
                    "\n\n"
                    + build_targeted_correction_prompt(
                        base_issues if continue_from_best else _structured_issues_from_exc(exc),
                        strategy,
                        strict=strict_mode,
                        meal_inventory=(
                            base_inventory
                            if continue_from_best
                            else exc.meal_inventory
                        ),
                        continue_from_best=continue_from_best,
                    )
                )
                continue
            except ClaudeJsonError as exc:
                logger.warning(
                    "generation_failed event=json_parse request_id=%s attempt=%s "
                    "error=%s stop_reason=%s raw_chars=%s",
                    request_id,
                    attempt,
                    str(exc),
                    stop_reason,
                    len(raw),
                )
                if strategy is None or attempt >= MAX_LLM_ATTEMPTS:
                    if stop_reason == "max_tokens":
                        raise ClaudeOutputTruncatedError(
                            "Claude output hit max_tokens mid-JSON",
                            stop_reason=stop_reason,
                            output_tokens=output_tokens,
                            raw_chars=len(raw),
                        ) from exc
                    raise
                if stop_reason == "max_tokens":
                    # Truncated mid-JSON: identical retry would truncate again.
                    compact_mode = True
                    correction_suffix = COMPACT_OUTPUT_INSTRUCTION
                    logger.warning(
                        "generation_retry request_id=%s event=output_truncated attempt=%s "
                        "retry_mode=compact_output",
                        request_id,
                        attempt,
                    )
                else:
                    logger.warning(
                        "generation_retry request_id=%s event=json_parse attempt=%s",
                        request_id,
                        attempt,
                    )
                    correction_suffix = (
                        "\n\nИСПРАВЛЕНИЕ: предыдущий ответ не был валидным JSON.\n"
                        "Верни ТОЛЬКО один полный JSON-объект меню без markdown-оградки "
                        "и без пояснений вокруг. Не обрезай ответ."
                    )
                continue
            except ClaudeValidationError as exc:
                if strategy is None or attempt >= MAX_LLM_ATTEMPTS:
                    raise
                logger.warning(
                    "generation_retry request_id=%s event=schema_validation attempt=%s "
                    "details=%s",
                    request_id,
                    attempt,
                    exc.details[:8],
                )
                detail_lines = "\n".join(f"- {item}" for item in (exc.details or [str(exc)])[:8])
                correction_suffix = (
                    "\n\nИСПРАВЛЕНИЕ: предыдущий JSON не прошёл schema validation.\n"
                    f"Ошибки:\n{detail_lines}\n"
                    "Исправь поля и верни полный валидный JSON по контракту меню."
                )
                continue

            logger.info(
                "generation_completed request_id=%s user_id=%s days=%s persons=%s "
                "strategy_version=%s compliance_passed=%s compact_mode=%s duration_ms=%s",
                request_id,
                user_id,
                days,
                persons,
                strategy.strategy_version if strategy else None,
                strategy is not None,
                compact_mode,
                int((time.monotonic() - started_at) * 1000),
            )

            shopping = shopping_cost_from_menu(result)
            budget_cap = float(strategy.budget) if strategy is not None else shopping
            usage_pct = usage_percent_from_shopping(shopping, budget_cap) if strategy else None

            # --- Budget optimizer convergence (shopping_cost authority) ---
            if budget_optimizer_active and budget_optimizer_baseline is not None:
                budget_optimizer_last_shopping = shopping
                valid_under_budget = is_shopping_within_budget(shopping, budget_cap)
                logger.info(
                    "budget_optimizer_candidate request_id=%s optimizer_attempt=%s "
                    "model_total=%s recipe_cost=%s shopping_cost=%s "
                    "usage_percent=%s valid=%s issue_codes=%s",
                    request_id,
                    budget_optimizer_corrections,
                    result.get("model_total"),
                    result.get("recipe_cost"),
                    shopping,
                    usage_pct,
                    valid_under_budget,
                    [],
                )

                if not valid_under_budget:
                    overshoot = max(0.0, shopping - budget_cap)
                    logger.info(
                        "budget_optimizer_rejected request_id=%s reason=over_budget "
                        "optimizer_attempt=%s authoritative_budget_cost=%s "
                        "budget_limit=%s overshoot_amount=%s",
                        request_id,
                        budget_optimizer_corrections,
                        shopping,
                        budget_cap,
                        overshoot,
                    )
                    if (
                        budget_optimizer_corrections < MAX_BUDGET_OPTIMIZER_CORRECTIONS
                        and attempt < MAX_LLM_ATTEMPTS
                        and budget_optimizer_target is not None
                    ):
                        budget_optimizer_feedback = build_budget_optimizer_feedback(
                            budget_limit=budget_cap,
                            previous_shopping_cost=shopping,
                            overshoot_amount=overshoot,
                            reason="over_budget",
                        )
                        budget_optimizer_corrections += 1
                        logger.info(
                            "budget_optimizer_attempt request_id=%s optimizer_attempt=%s "
                            "previous_shopping_cost=%s desired_delta=%s",
                            request_id,
                            budget_optimizer_corrections,
                            budget_optimizer_target.current_cost,
                            budget_optimizer_target.desired_delta,
                        )
                        correction_suffix = build_budget_optimizer_prompt(
                            budget_limit=budget_cap,
                            shopping_cost=budget_optimizer_target.current_cost,
                            target=budget_optimizer_target,
                            feedback=budget_optimizer_feedback,
                            previous_model_total=(
                                float(result["model_total"])
                                if isinstance(result.get("model_total"), (int, float))
                                else None
                            ),
                        )
                        continue
                    final = budget_optimizer_best or budget_optimizer_baseline
                    logger.info(
                        "budget_optimizer_completed request_id=%s accepted=False "
                        "attempts=%s reason=over_budget "
                        "initial_shopping_cost=%s final_shopping_cost=%s "
                        "initial_usage_percent=%s final_usage_percent=%s",
                        request_id,
                        budget_optimizer_corrections,
                        budget_optimizer_baseline.get("shopping_cost"),
                        final.get("shopping_cost"),
                        budget_optimizer_baseline.get("budget_usage_percent"),
                        final.get("budget_usage_percent"),
                    )
                    return _succeed(final)

                baseline_shopping = shopping_cost_from_menu(budget_optimizer_baseline)
                if is_better_budget_candidate(
                    candidate_shopping=shopping,
                    baseline_shopping=shopping_cost_from_menu(
                        budget_optimizer_best or budget_optimizer_baseline
                    ),
                    budget_limit=budget_cap,
                ):
                    budget_optimizer_best = result

                if is_shopping_in_target(shopping, budget_cap):
                    logger.info(
                        "budget_optimizer_completed request_id=%s accepted=True "
                        "attempts=%s reason=in_target "
                        "initial_shopping_cost=%s final_shopping_cost=%s "
                        "initial_usage_percent=%s final_usage_percent=%s",
                        request_id,
                        budget_optimizer_corrections,
                        budget_optimizer_baseline.get("shopping_cost"),
                        shopping,
                        budget_optimizer_baseline.get("budget_usage_percent"),
                        usage_pct,
                    )
                    return _succeed(result)

                if improvement_is_negligible(
                    previous_shopping=baseline_shopping,
                    new_shopping=shopping,
                    budget_limit=budget_cap,
                ):
                    final = budget_optimizer_best or budget_optimizer_baseline
                    logger.info(
                        "budget_optimizer_completed request_id=%s accepted=%s "
                        "attempts=%s reason=negligible_improvement "
                        "initial_shopping_cost=%s final_shopping_cost=%s "
                        "initial_usage_percent=%s final_usage_percent=%s",
                        request_id,
                        final is not budget_optimizer_baseline,
                        budget_optimizer_corrections,
                        budget_optimizer_baseline.get("shopping_cost"),
                        final.get("shopping_cost"),
                        budget_optimizer_baseline.get("budget_usage_percent"),
                        final.get("budget_usage_percent"),
                    )
                    return _succeed(final)

                if (
                    budget_optimizer_corrections < MAX_BUDGET_OPTIMIZER_CORRECTIONS
                    and attempt < MAX_LLM_ATTEMPTS
                    and budget_optimizer_target is not None
                ):
                    budget_optimizer_feedback = build_budget_optimizer_feedback(
                        budget_limit=budget_cap,
                        previous_shopping_cost=shopping,
                        reason="below_target",
                    )
                    budget_optimizer_corrections += 1
                    logger.info(
                        "budget_optimizer_attempt request_id=%s optimizer_attempt=%s "
                        "previous_shopping_cost=%s desired_delta=%s",
                        request_id,
                        budget_optimizer_corrections,
                        shopping,
                        max(0.0, budget_optimizer_target.preferred_target - shopping),
                    )
                    correction_suffix = build_budget_optimizer_prompt(
                        budget_limit=budget_cap,
                        shopping_cost=shopping,
                        target=compute_budget_optimization_target(shopping, budget_cap),
                        feedback=budget_optimizer_feedback,
                        previous_model_total=(
                            float(result["model_total"])
                            if isinstance(result.get("model_total"), (int, float))
                            else None
                        ),
                    )
                    continue

                final = budget_optimizer_best or budget_optimizer_baseline
                accepted = final is not budget_optimizer_baseline and is_better_budget_candidate(
                    candidate_shopping=shopping_cost_from_menu(final),
                    baseline_shopping=baseline_shopping,
                    budget_limit=budget_cap,
                )
                logger.info(
                    "budget_optimizer_completed request_id=%s accepted=%s "
                    "attempts=%s reason=exhausted "
                    "initial_shopping_cost=%s final_shopping_cost=%s "
                    "initial_usage_percent=%s final_usage_percent=%s",
                    request_id,
                    accepted,
                    budget_optimizer_corrections,
                    budget_optimizer_baseline.get("shopping_cost"),
                    final.get("shopping_cost"),
                    budget_optimizer_baseline.get("budget_usage_percent"),
                    final.get("budget_usage_percent"),
                )
                return _succeed(final)

            if (
                strategy is not None
                and config.BUDGET_OPTIMIZER_ENABLED
                and not budget_optimizer_active
                and attempt < MAX_LLM_ATTEMPTS
                and should_start_budget_optimizer(shopping, budget_cap)
            ):
                target = compute_budget_optimization_target(shopping, budget_cap)
                if target is not None:
                    budget_optimizer_active = True
                    budget_optimizer_corrections = 1
                    budget_optimizer_baseline = result
                    budget_optimizer_best = result
                    budget_optimizer_target = target
                    budget_optimizer_last_shopping = shopping
                    await _emit_generation_progress(
                        progress_callback,
                        stage="optimizing_budget",
                        attempt=attempt,
                        max_attempts=MAX_LLM_ATTEMPTS,
                    )
                    logger.info(
                        "budget_optimizer_started request_id=%s budget_limit=%s "
                        "initial_shopping_cost=%s initial_usage_percent=%s "
                        "target_min=%s target_preferred=%s target_max=%s",
                        request_id,
                        target.budget_limit,
                        target.current_cost,
                        target.usage_percent,
                        target.min_target,
                        target.preferred_target,
                        target.max_target,
                    )
                    logger.info(
                        "budget_optimizer_attempt request_id=%s optimizer_attempt=%s "
                        "previous_shopping_cost=%s desired_delta=%s",
                        request_id,
                        budget_optimizer_corrections,
                        target.current_cost,
                        target.desired_delta,
                    )
                    correction_suffix = build_budget_optimizer_prompt(
                        budget_limit=target.budget_limit,
                        shopping_cost=target.current_cost,
                        usage_percent=target.usage_percent,
                        target=target,
                        previous_model_total=(
                            float(result["model_total"])
                            if isinstance(result.get("model_total"), (int, float))
                            else None
                        ),
                    )
                    continue

            return _succeed(result)

        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning(
                "generation_failed request_id=%s event=timeout attempt=%s duration_ms=%s",
                request_id,
                attempt,
                int((time.monotonic() - started_at) * 1000),
            )
            await asyncio.sleep(5)
        except (
            ClaudeJsonError,
            ClaudeValidationError,
            MenuConstraintError,
            ClaudeOutputTruncatedError,
        ) as exc:
            _log_reliability(f"failed:{type(exc).__name__}")
            raise
        except ClaudeUnavailableError:
            _log_reliability("failed:ClaudeUnavailableError")
            raise
        except Exception as exc:
            last_error = exc
            # Full traceback: this is the catch-all that previously hid root causes.
            logger.exception(
                "generation_failed request_id=%s event=unexpected error=%s duration_ms=%s",
                request_id,
                type(exc).__name__,
                int((time.monotonic() - started_at) * 1000),
            )
            _log_reliability("failed:unexpected")
            raise ClaudeUnavailableError("Unexpected Claude processing error") from exc

    _log_reliability("failed:timeout")
    raise ClaudeTimeoutError("Claude request timed out") from last_error
