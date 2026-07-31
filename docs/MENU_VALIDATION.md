# Menu Validation

Server-side validation for Claude menu generation responses.

## Pipeline

```
Claude response text
  → extract_json_object()        # claude_json.py
  → normalize_days_plan_payload() # meal_types.py (legacy → meals[])
  → MenuPlan.model_validate()    # menu_models.py (Pydantic)
  → validate_menu_plan()         # menu_validation.py
  → API JSON response
```

Invalid menus are **not** returned to the frontend. The API responds with HTTP **502** and a generic user message.

## Meal types contract

`request.meal_types` is the **primary** source for which meal slots must appear in each day.

Supported values: `breakfast`, `lunch`, `dinner`, `snack`.

- At least one meal type must be selected in the profile/request.
- Each day must contain **exactly one** entry per selected type in `days_plan[].meals[]`.
- `request.meals_per_day` is **deprecated** for business logic; the server recalculates it as `len(meal_types)` and ignores mismatched client values.

### Backward compatibility

| Source | Fallback |
|--------|----------|
| Profile without `meal_types` | `["breakfast", "lunch", "dinner"]` |
| Request with only `meals_per_day` | `1→breakfast`, `2→breakfast+dinner`, `3→breakfast+lunch+dinner`, `4+→+snack` |
| Legacy Claude `breakfast/lunch/dinner` | Converted to `meals[]` before validation |
| `snack` requested but legacy response | `MEAL_TYPE_MISSING` error |

## Day plan structure

Primary contract:

```json
{
  "day": "День 1",
  "meals": [
    { "type": "breakfast", "recipe_name": "Овсянка" },
    { "type": "dinner", "recipe_name": "Рыба с овощами" }
  ]
}
```

For temporary compatibility, `breakfast`, `lunch`, and `dinner` legacy string fields are still populated from `meals[]` in API responses.

## Budget semantics

`request.budget` is the **total budget for the entire planning period** (all days), not per day.

- Tolerance for exceeding budget: **0 ₽**
- `total_cost` must match the sum of `basket[].items[].price` within **±1 ₽** (rounding)

## Cooktime limits

| Request `cooktime` | Max minutes per recipe |
|--------------------|------------------------|
| `fast`             | 20                     |
| `medium`           | 45                     |
| `slow`             | 90                     |

Ranges like `20–30 минут` use the **upper** bound.

## Issue codes

| Code | Severity | Blocks response |
|------|----------|-----------------|
| `DAYS_COUNT_MISMATCH` | error | yes |
| `MEAL_TYPE_MISSING` | error | yes |
| `MEAL_TYPE_UNEXPECTED` | error | yes |
| `MEAL_TYPE_DUPLICATE` | error | yes |
| `MEAL_RECIPE_MISSING` | error | yes |
| `MEAL_RECIPE_AMBIGUOUS` | error | yes |
| `RECIPE_UNUSED` | warning | no |
| `BUDGET_EXCEEDED` | error | yes |
| `TOTAL_COST_MISMATCH` | error | yes |
| `ALLERGY_VIOLATION` | error | yes |
| `COOKTIME_EXCEEDED` | error | yes |
| `COOKTIME_UNPARSEABLE` | warning | no |
| `MEAL_DUPLICATE_WARNING` | warning | no |
| `MEAL_DUPLICATE_EXCESSIVE` | error | yes |
| `BASKET_INGREDIENT_MISSING` | warning | no |

Unknown `meal.type` values are rejected by Pydantic schema validation (`ClaudeValidationError`) before constraint validation.

## Meal ↔ recipe matching

Uses normalized name comparison (trim, lower, ё→е, punctuation, meal prefixes). Only **exact** or **normalized unique** matches are accepted. Ambiguous or missing matches are errors.

## Allergy checks

`allergies` is a free-form string split by commas/semicolons. Obvious alias groups (e.g. `молоко` → `сыр`, `творог`) are checked in meal names, recipe ingredients, and basket item names.

## Pantry staples (basket warnings excluded)

`sоль`, `вода`, `перец`, `масло`, `специи` (and close variants).

## API error responses

| Condition | HTTP | User message |
|-----------|------|--------------|
| Timeout | 504 | Генерация заняла слишком много времени… |
| Claude unavailable | 503 | Сервис генерации временно недоступен. |
| Invalid JSON / schema / constraints | 502 | Не удалось сформировать корректное меню… |

Internal issue codes are logged in non-production environments only.

## Not strictly verifiable without API changes

- **Servings per recipe** — `Recipe` has no `servings` field; persons is only enforced via prompt
- **Semantic duplicate dishes** (e.g. «борщ» vs «суп с капустой»)
- **Medical allergy synonyms** beyond explicit alias map
- **Store-specific pricing accuracy**
