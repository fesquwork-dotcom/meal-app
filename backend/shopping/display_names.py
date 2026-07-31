"""Human-readable ingredient names and rare-ingredient glossary (presentation only)."""

from __future__ import annotations

import re

from menu_models import normalize_meal_name

# Common grocery names: canonical key → preferred display label.
DISPLAY_NAME_MAP: dict[str, str] = {
    "помидор": "Помидоры",
    "томат": "Помидоры",
    "томаты": "Помидоры",
    "огурец": "Огурцы",
    "огурцы": "Огурцы",
    "лук": "Лук",
    "лук репчатый": "Лук",
    "морковь": "Морковь",
    "картофель": "Картофель",
    "картошка": "Картофель",
    "чеснок": "Чеснок",
    "куриная грудка": "Куриное филе",
    "куриное филе": "Куриное филе",
    "филе курицы": "Куриное филе",
    "говядина": "Говядина",
    "свинина": "Свинина",
    "индейка": "Индейка",
    "рис": "Рис",
    "гречка": "Гречка",
    "гречневая крупа": "Гречка",
    "булгур": "Булгур",
    "киноа": "Киноа",
    "нут": "Нут",
    "чечевица": "Чечевица",
    "молоко": "Молоко",
    "яйцо": "Яйца",
    "яйца": "Яйца",
    "сыр": "Сыр",
    "творог": "Творог",
    "сметана": "Сметана",
    "масло сливочное": "Сливочное масло",
    "масло растительное": "Растительное масло",
    "оливковое масло": "Оливковое масло",
    "соль": "Соль",
    "сахар": "Сахар",
    "мука": "Мука",
    "паприка": "Паприка",
    "чёрный перец": "Чёрный перец",
    "черный перец": "Чёрный перец",
    "перец черный": "Чёрный перец",
    "перец чёрный": "Чёрный перец",
    "тахини": "Тахини",
    "кумин": "Кумин",
    "кориандр": "Кориандр",
    "куркума": "Куркума",
    "базилик": "Базилик",
    "укроп": "Укроп",
    "петрушка": "Петрушка",
    "шпинат": "Шпинат",
    "авокадо": "Авокадо",
    "капуста": "Капуста",
    "брокколи": "Брокколи",
    "кабачок": "Кабачки",
    "кабачки": "Кабачки",
    "баклажан": "Баклажаны",
    "баклажаны": "Баклажаны",
    "перец болгарский": "Болгарский перец",
    "болгарский перец": "Болгарский перец",
    "грибы": "Грибы",
    "шампиньоны": "Шампиньоны",
    "лосось": "Лосось",
    "треска": "Треска",
    "тунец": "Тунец",
    "креветки": "Креветки",
    "макароны": "Макароны",
    "паста": "Паста",
    "хлеб": "Хлеб",
    "лаваш": "Лаваш",
    "йогурт": "Йогурт",
    "кефир": "Кефир",
    "мед": "Мёд",
    "мёд": "Мёд",
    "лимон": "Лимон",
    "лайм": "Лайм",
    "имбирь": "Имбирь",
    "соевый соус": "Соевый соус",
}

# Rare / less familiar ingredients → short explanation shown under the name.
INGREDIENT_GLOSSARY: dict[str, str] = {
    "тахини": "кунжутная паста",
    "тахин": "кунжутная паста",
    "булгур": "пшеничная крупа",
    "киноа": "зерновая культура",
    "нут": "турецкий горох",
    "мисо": "паста из ферментированных соевых бобов",
    "паста мисо": "паста из ферментированных соевых бобов",
    "кокосовое молоко": "молоко из мякоти кокоса",
    "гарам масала": "смесь индийских специй",
    "харрисса": "острая перечная паста",
    "харисса": "острая перечная паста",
    "тамаринд": "кисло-сладкая паста из плодов тамаринда",
    "суммах": "кислая ягодная приправа",
    "сумах": "кислая ягодная приправа",
    "кускус": "пшеничная крупа мелкого помола",
    "тофу": "соевый творог",
    "темпе": "ферментированный соевый продукт",
    "кимчи": "корейская квашеная капуста",
    "васаби": "острая японская приправа",
    "нори": "листы сушёных водорослей",
    "мирин": "сладкое рисовое вино",
    "саке": "рисовое вино",
    "фисташки": "орехи",
    "кешью": "орехи",
    "кедровые орехи": "орехи",
}

_HYPHEN_PATTERN = re.compile(r"[-–—]+")


def _lookup_key(name: str) -> str:
    normalized = normalize_meal_name(name)
    normalized = _HYPHEN_PATTERN.sub(" ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def resolve_display_name(name: str) -> str:
    """Prefer common grocery wording; never expose raw canonical keys."""
    stripped = name.strip()
    if not stripped:
        return stripped

    key = _lookup_key(stripped)
    if key in DISPLAY_NAME_MAP:
        return DISPLAY_NAME_MAP[key]

    # Whole-word soft match only (avoids "лук" matching "булгур").
    soft: list[tuple[str, str]] = []
    for alias, mapped in DISPLAY_NAME_MAP.items():
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", key):
            soft.append((alias, mapped))
    if soft:
        soft.sort(key=lambda pair: len(pair[0]), reverse=True)
        return soft[0][1]

    return pretty_ingredient_name(stripped)


def pretty_ingredient_name(name: str) -> str:
    """Capitalize for display when no dictionary entry exists."""
    stripped = name.strip()
    if not stripped:
        return stripped
    # Avoid shouting ALL-CAPS; title-case first letter only.
    return stripped[0].upper() + stripped[1:]


def glossary_note(name: str) -> str | None:
    """Return a short explanation for uncommon ingredients, or None."""
    key = _lookup_key(name)
    if key in INGREDIENT_GLOSSARY:
        return INGREDIENT_GLOSSARY[key]
    soft: list[tuple[str, str]] = []
    for alias, note in INGREDIENT_GLOSSARY.items():
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", key):
            soft.append((alias, note))
    if soft:
        soft.sort(key=lambda pair: len(pair[0]), reverse=True)
        return soft[0][1]
    return None
