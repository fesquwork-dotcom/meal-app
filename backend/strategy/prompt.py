"""Serialize WeeklyStrategy for Claude prompts."""

from __future__ import annotations

import json

from strategy.models import WeeklyStrategy

RECIPE_ID_CONTRACT = """═══ RECIPE IDENTITY (обязателен при WEEKLY_STRATEGY) ═══
Каждый Recipe и DayMeal содержит recipe_id — стабильный ID в пределах меню.
- Формат: recipe_day1_dinner, recipe_day2_lunch (детерминированный, без UUID)
- meal_id и recipe_id — разные сущности: meal_id = позиция в плане, recipe_id = рецепт
- Каждый meal.recipe_id ссылается на существующий recipe.recipe_id
- recipe_id уникален среди recipes[]
- recipe_name остаётся display text и должен совпадать с recipe.name
- Несколько meals могут ссылаться на один recipe_id только при batch/leftover логике
- Каждое независимое приготовление — отдельный recipe_id

═══ INGREDIENT CONTRIBUTION (обязателен при WEEKLY_STRATEGY) ═══
Каждый ingredient содержит contribution:
- purchase — включить в корзину (обычные ингредиенты)
- from_source — из ранее приготовленного (только leftover meals с source_meal_id)
- pantry — базовый запас, разрешён ТОЛЬКО если название ингредиента буквально:
  соль, вода, перец, масло (растительное/оливковое/подсолнечное), специи
- Именованные специи и добавки (паприка, кумин, корица, зелень, чеснок, сахар,
  мёд, соевый соус, лимонный сок и т.п.) — ВСЕГДА purchase, НЕ pantry

Leftover meal (uses_leftovers=true) должен иметь хотя бы один from_source ingredient.
Остальные свежие ингредиенты leftover meal — purchase."""

CONTRIBUTION_CORRECTION_RULE = """ПРАВИЛО INGREDIENT CONTRIBUTION (исправь ВСЕ ингредиенты, не только перечисленные):
- contribution может быть только: "purchase" | "from_source" | "pantry"
- "pantry" допустим ТОЛЬКО если название ингредиента буквально одно из:
  соль, вода, перец, масло (растительное/оливковое/подсолнечное), специи
- Любая именованная специя или добавка (паприка, кумин, корица, зелень, чеснок,
  сахар, мёд, фета, соевый соус, лимонный сок и т.п.) — "purchase"
- "from_source" — только в leftover meals (uses_leftovers=true с source_meal_id)"""

COOKING_INSTANCE_CONTRACT = """═══ COOKING INSTANCE (обязателен при WEEKLY_STRATEGY) ═══
Каждый meal содержит cooking_instance_id — идентификатор одной фактической готовки.
- Формат: cook_day1_dinner, batch_chicken_day1 (детерминированный, без UUID)
- recipe_id описывает ЧТО готовить; cooking_instance_id описывает КОГДА готовили
- source meal и leftover meal с общей основой используют ОДНУ cooking_instance_id
- независимое повторное приготовление того же recipe_id — новая cooking_instance_id
- одинаковый recipe_id НЕ означает одну готовку автоматически
- все meals с одной instance имеют одинаковый prepared_on_day"""

COOKING_CONTRACT_INSTRUCTIONS = """═══ COOKING CONTRACT (обязателен при WEEKLY_STRATEGY) ═══
Каждый элемент meals[] должен содержать:
- meal_id: уникальный ID в пределах меню (например day1_dinner);
- cooking_instance_id: ID одной фактической готовки (например cook_day1_dinner);
- requires_cooking: true если нужна новая активная готовка, false для разогрева/сборки/остатков;
- prepared_on_day: день периода (1..days), когда блюдо или его база приготовлены;
- uses_leftovers: true если реально переиспользуется ранее приготовленная основа;
- source_meal_id: ID источника (обязателен при uses_leftovers=true).

Правила:
- Новая готовка (requires_cooking=true) разрешена ТОЛЬКО в cook_days.
- В дни вне cook_days requires_cooking должно быть false.
- Разогрев и сборка не считаются новой готовкой.
- source_meal_id ссылается на существующий meal_id более раннего дня.
- Нельзя ссылаться на будущие блюда или создавать циклы.
- При leftovers_enabled=true создай хотя бы одну валидную leftover-связь, если период > 1 дня.
- При leftovers_enabled=false не создавай искусственные leftover-связи.
- Допускается трансформация источника (курица с овощами → боул с курицей)."""

STRATEGY_AUTHORITY_INSTRUCTIONS = """═══ WEEKLY STRATEGY (AUTHORITATIVE) ═══
Стратегия недели обязательна. Не переосмысливай, не заменяй, не оптимизируй в обход неё и не противоречь ей.
Твоя задача — исполнить стратегию: подобрать конкретные блюда, рецепты и ингредиенты в формате JSON.

Claude ДОЛЖЕН:
- создавать конкретные блюда и рецепты;
- подбирать ингредиенты и порции;
- соблюдать JSON-контракт ответа;
- соблюдать все ограничения WEEKLY_STRATEGY.

Claude НЕ ДОЛЖЕН:
- менять количество дней или типы приёмов пищи;
- увеличивать бюджет;
- добавлять исключённые продукты;
- менять цель (goal);
- игнорировать cook_days;
- отменять разрешённые повторы или обязательное переиспользование остатков.

Приоритет ограничений:
1. аллергии и исключения;
2. структура дней и meal_types;
3. безопасность и валидность JSON;
4. бюджет (total_cost корзины ≤ budget; стремись к 90–100% использования бюджета);
5. cooking_time_limit (активное время готовки);
6. cook_days;
7. leftovers / repeat flags;
8. разнообразие.

Бюджет — вторичный критерий качества после безопасности и стратегии:
- не превышай budget;
- по возможности используй 90–100% бюджета за счёт качества продуктов, а не лишних блюд или порций;
- не добавляй блюда только чтобы потратить деньги.

cook_days — дни периода (1..days), когда пользователь готовит новое блюдо или базовую заготовку.
В дни ВНЕ cook_days используй: остатки, повтор, сборное блюдо, блюдо без полноценного приготовления.
Не назначай сложное новое приготовление каждый день, если стратегия это не разрешает.

leftovers_enabled=true: осмысленно переиспользуй приготовленные блюда или компоненты (курица в нескольких блюдах, крупа на 2 дня, суп повторно, общий соус).
leftovers_enabled=false: не требуй искусственного переиспользования.

repeat_breakfasts/lunches/dinners=true: можно и нужно повторять блюда этого типа для бюджета, времени и cook_days.
repeat_*=false: минимизируй точные повторы блюд этого типа, но не нарушай более приоритетные ограничения.

cooking_time_limit — максимальное АКТИВНОЕ время приготовления одной сессии в минутах.
Пассивное ожидание (варка, запекание без участия) может быть дольше.
Batch cooking в cook_days разрешён.

prefer_faster_meals=true: при прочих равных выбирай блюда с меньшим активным временем
приготовления, не превышая cooking_time_limit и не нарушая другие ограничения.

availability_avoid_products — мягкое ограничение доступности продуктов.
По возможности не используй эти продукты. Оно не имеет приоритета над обязательными
ограничениями, бюджетом и полнотой меню. Если без них невозможно составить план
в рамках остальных обязательных ограничений, допускается использовать их как последнее средство.

prefer_familiar_meals=true: при прочих равных выбирай знакомые, понятные и широко
распространённые блюда. Не уменьшай обязательное разнообразие, не нарушай meal types,
dietary constraints, budget, cook_days или cooking time limit.

shopping_days — стратегическое ограничение закупок: группируй продукты корзины под указанные дни; скоропорт на вторую половину периода не покупай в первый день."""

COOK_DAYS_SEMANTICS = """Дни периода нумеруются с 1 до days включительно. cook_days и shopping_days — индексы внутри этого периода."""


def strategy_to_prompt_dict(strategy: WeeklyStrategy) -> dict[str, object]:
    """Returns JSON-serializable strategy payload for prompts (no internal fields)."""
    return {
        "strategy_version": strategy.strategy_version,
        "goal": strategy.goal,
        "days": strategy.days,
        "budget": strategy.budget,
        "meal_types": list(strategy.meal_types),
        "cook_days": list(strategy.cook_days),
        "shopping_days": list(strategy.shopping_days),
        "leftovers_enabled": strategy.leftovers_enabled,
        "repeat_breakfasts": strategy.repeat_breakfasts,
        "repeat_lunches": strategy.repeat_lunches,
        "repeat_dinners": strategy.repeat_dinners,
        "preferred_proteins": list(strategy.preferred_proteins),
        "excluded_products": list(strategy.excluded_products),
        "cooking_time_limit": strategy.cooking_time_limit,
        "prefer_faster_meals": strategy.prefer_faster_meals,
        "availability_avoid_products": list(strategy.availability_avoid_products),
        "prefer_familiar_meals": strategy.prefer_familiar_meals,
    }


def build_strategy_prompt_section(strategy: WeeklyStrategy) -> str:
    """Builds structured WEEKLY_STRATEGY section for Claude user prompt."""
    payload = json.dumps(
        strategy_to_prompt_dict(strategy),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return (
        "WEEKLY_STRATEGY (обязательный контракт, JSON):\n"
        f"{payload}\n"
        f"{COOK_DAYS_SEMANTICS}"
    )


def build_strategy_system_section() -> str:
    """System-prompt block defining strategy authority."""
    return STRATEGY_AUTHORITY_INSTRUCTIONS + "\n" + RECIPE_ID_CONTRACT + "\n" + COOKING_INSTANCE_CONTRACT + "\n" + COOKING_CONTRACT_INSTRUCTIONS


def build_correction_prompt(
    issue_codes: list[str],
    messages: list[str],
    strategy: WeeklyStrategy,
) -> str:
    """Builds a correction instruction appended on compliance/menu retry."""
    violations = "\n".join(f"- {code}: {msg}" for code, msg in zip(issue_codes, messages))
    contribution_rule = (
        f"\n{CONTRIBUTION_CORRECTION_RULE}\n"
        if "INGREDIENT_CONTRIBUTION_INVALID" in issue_codes
        else ""
    )
    return (
        "ИСПРАВЛЕНИЕ: предыдущий ответ нарушил стратегию или контракт меню.\n"
        f"Нарушения:\n{violations}\n"
        f"{contribution_rule}\n"
        f"{build_strategy_prompt_section(strategy)}\n\n"
        "Исправь только нарушения. Сохрани тот же JSON-контракт. "
        "Не меняй стратегию. Верни полный исправленный JSON."
    )


def _format_duplicate_positions(positions: list[object]) -> str:
    parts: list[str] = []
    for position in positions:
        if not isinstance(position, dict):
            continue
        day = position.get("day")
        meal_type = position.get("meal_type")
        meal_id = position.get("meal_id")
        label = f"день {day}, {meal_type}"
        if meal_id:
            label += f" ({meal_id})"
        parts.append(label)
    return "; ".join(parts)


def _cooktime_instruction(message: str, meta: dict[str, object]) -> str:
    recipe_id = meta.get("recipe_id") or meta.get("recipe_title") or "рецепт"
    title = meta.get("recipe_title") or ""
    actual = meta.get("actual_minutes")
    allowed = meta.get("allowed_minutes")
    meal_ids = meta.get("meal_ids") or []
    if actual is None or allowed is None:
        return f"- COOKTIME_EXCEEDED: {message}"
    linked = f" Связанные приёмы пищи: {', '.join(str(m) for m in meal_ids)}." if meal_ids else ""
    return (
        f"- Рецепт {recipe_id}"
        + (f" («{title}»)" if title else "")
        + f" имеет cook_time={actual} мин, допустимый максимум {allowed} мин.\n"
        f"  Упрости или замени ТОЛЬКО этот рецепт так, чтобы cook_time <= {allowed} мин."
        f"{linked}\n"
        "  Рецепт должен реально готовиться за это время — не просто уменьшай число cook_time.\n"
        "  Не меняй остальные валидные рецепты."
    )


def _duplicate_instruction(message: str, meta: dict[str, object]) -> str:
    meal_name = meta.get("meal_name") or meta.get("duplicate_key") or "блюдо"
    independent = meta.get("independent_count")
    allowed = meta.get("allowed_count")
    replacements = meta.get("replacements_needed")
    positions = meta.get("independent_positions")
    meal_types = meta.get("meal_types")
    if independent is None or allowed is None or replacements is None:
        return f"- MEAL_DUPLICATE_EXCESSIVE: {message}"
    positions_text = (
        _format_duplicate_positions(positions) if isinstance(positions, list) else ""
    )
    positions_line = f"\n  Позиции: {positions_text}." if positions_text else ""
    type_hint = ""
    if isinstance(meal_types, list) and meal_types:
        type_hint = f" того же типа ({', '.join(str(t) for t in meal_types)})"
    return (
        f"- Блюдо «{meal_name}» используется {independent} раз(а) независимо, "
        f"допустимый максимум {allowed}.{positions_line}\n"
        f"  Замени РОВНО {replacements} из этих позиций на РАЗНЫЕ блюда{type_hint}.\n"
        "  Остальные позиции этого блюда оставь без изменений.\n"
        "  Не уменьшай разнообразие других типов приёмов пищи и не заменяй исправление массовыми leftovers."
    )


def _format_meal_usage_section(inventory: dict[str, object] | None) -> str:
    """Forbidden + preferred replacement pools derived from the rejected plan."""
    if not inventory:
        return ""
    used = inventory.get("used") or []
    at_limit = inventory.get("at_limit") or []
    once_used = inventory.get("once_used") or []
    allowed = inventory.get("allowed_count", 2)

    used_lines: list[str] = []
    if isinstance(used, list):
        for entry in used:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            count = entry.get("count")
            if name is None or count is None:
                continue
            used_lines.append(f"  - {name} (×{count})")

    at_limit_lines = [f"  - {name}" for name in at_limit] if isinstance(at_limit, list) else []
    once_lines = [f"  - {name}" for name in once_used] if isinstance(once_used, list) else []

    if not used_lines and not at_limit_lines and not once_lines:
        return ""

    parts = [
        "═══ ИНВЕНТАРЬ БЛЮД (для детерминированной замены) ═══",
        f"allowed_count = {allowed} независимых использований на одно блюдо.",
    ]
    if used_lines:
        parts.append("Уже используются (независимые приёмы):")
        parts.extend(used_lines)
    if at_limit_lines:
        parts.append(
            "ЗАПРЕЩЕНО выбирать как замену (уже на лимите — новый повтор создаст "
            "MEAL_DUPLICATE_EXCESSIVE):"
        )
        parts.extend(at_limit_lines)
    if once_lines:
        parts.append(
            "Допустимые уникальные блюда для замены (использованы ровно 1 раз — "
            "можно выбрать одно из них ИЛИ придумать НОВОЕ имя, которого нет в списке «Уже используются»):"
        )
        parts.extend(once_lines)
    else:
        parts.append(
            "Список однократных блюд пуст — замена должна быть НОВЫМ именем, "
            "которого нет в списке «Уже используются»."
        )
    parts.append(
        "Правило: при замене НЕ выбирай блюда из запрещённого списка. "
        "Не создавай второе новое блюдо, которое само начнёт повторяться в других днях."
    )
    return "\n".join(parts) + "\n"


def build_targeted_correction_prompt(
    issues: list[dict[str, object]],
    strategy: WeeklyStrategy,
    *,
    strict: bool = False,
    meal_inventory: dict[str, object] | None = None,
    continue_from_best: bool = False,
) -> str:
    """Per-issue correction: tells the model exactly what to change and what to keep.

    Each issue dict has keys: code, message, and optional meta (validator diagnostics).
    meal_inventory (optional) lists used / at-limit / once-used meals so replacements
    do not invent a new duplicate.
    """
    instructions: list[str] = []
    codes: list[str] = []
    for issue in issues:
        code = str(issue.get("code") or "")
        message = str(issue.get("message") or "")
        meta = issue.get("meta")
        meta_dict = meta if isinstance(meta, dict) else {}
        codes.append(code)
        if code == "COOKTIME_EXCEEDED":
            instructions.append(_cooktime_instruction(message, meta_dict))
        elif code == "MEAL_DUPLICATE_EXCESSIVE":
            instructions.append(_duplicate_instruction(message, meta_dict))
        else:
            instructions.append(f"- {code}: {message}")

    contribution_rule = (
        f"\n{CONTRIBUTION_CORRECTION_RULE}\n"
        if "INGREDIENT_CONTRIBUTION_INVALID" in codes
        else ""
    )

    total_meals = strategy.days * len(strategy.meal_types)
    if strict and continue_from_best:
        header = (
            "СТРОГОЕ ИСПРАВЛЕНИЕ (финальная попытка, база = лучший предыдущий кандидат): "
            "последний retry ухудшил результат и ОТБРОШЕН. "
            "Исправь проблемы лучшего кандидата ниже, не повторяя ошибки отброшенного retry."
        )
    elif strict:
        header = (
            "СТРОГОЕ ИСПРАВЛЕНИЕ (финальная попытка): предыдущие ответы нарушили контракт меню. "
            "Устрани ВСЕ перечисленные проблемы одновременно, ничего не пропуская."
        )
    elif continue_from_best:
        header = (
            "ИСПРАВЛЕНИЕ (база = лучший предыдущий кандидат): последний retry ухудшил результат "
            "и отброшен. Исправь ТОЛЬКО проблемы лучшего кандидата ниже."
        )
    else:
        header = (
            "ИСПРАВЛЕНИЕ: предыдущий ответ нарушил контракт меню. "
            "Исправь ТОЛЬКО перечисленные проблемы."
        )
    issue_block = "\n".join(instructions)
    inventory_section = _format_meal_usage_section(meal_inventory)

    return (
        f"{header}\n"
        "Return the full valid JSON document, but modify only the items explicitly listed below.\n"
        f"Проблемы:\n{issue_block}\n"
        f"{inventory_section}"
        f"{contribution_rule}\n"
        "Правила сохранения (обязательно):\n"
        "- сохрани все корректные дни, приёмы пищи и рецепты БЕЗ изменений;\n"
        "- сохрани meal_id, recipe_id и cooking_instance_id всех неизменяемых элементов;\n"
        f"- сохрани ровно {strategy.days} дней и {total_meals} приёмов пищи;\n"
        f"- сохрани обязательные типы приёмов пищи: {', '.join(strategy.meal_types)};\n"
        "- НЕ уменьшай количество уникальных рецептов;\n"
        "- НЕ превращай исправление отдельных позиций в массовое использование leftovers;\n"
        "- НЕ переписывай всё меню заново.\n\n"
        f"{build_strategy_prompt_section(strategy)}\n\n"
        "Верни полный исправленный JSON по тому же контракту."
    )
