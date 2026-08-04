# Recipe Quality Workflow (Sprint 10.7)

This document describes the safe process for adding recipes after the Quality & Provenance layer is in place.

## Concepts (do not mix)

| Concept | Purpose |
|---------|---------|
| `RecipeStatus` | Technical catalog availability: `draft` → `validated` → `active` → `archived` |
| `QualityStatus` | Trust in content: `unreviewed` … `approved` / `rejected` |
| `CreationMethod` | How the recipe was created (`agent_generated`, `source_adapted`, …) |

An active recipe can still be `agent_generated` + `schema_validated`. That does **not** mean it is approved.

## Recommended pipeline

```text
1. Draft recipe concept
2. Collect ≥2 real independent sources (cookbook, reputable site, manufacturer, expert notes)
3. Author a normalized catalog YAML (do not copy blindly)
4. Record provenance + recipe_sources (real references only — never invent URLs)
5. Schema validation (`import --mode dry_run` / `validate_only`)
6. Computational quality audit (`quality-audit`)
7. Metadata review (tags, roles, goal scores vs pattern evidence)
8. Human culinary review (record recipe_quality_reviews)
9. Optional kitchen test for priority / storage / batch claims
10. Human approval → QualityStatus.approved
11. Publish / keep RecipeStatus.active
```

## Quality status rules (summary)

- `schema_validated` — catalog schema & references OK
- `computationally_checked` — no blocking computational errors; warnings allowed
- `source_verified` — ≥1 real `recipe_sources` row + source review passed
- `human_reviewed` / `kitchen_tested` — corresponding review records
- `approved` — computationally checked + source verified + (human or kitchen) + human approval fields

Automatic audit / CLI `--apply` may raise **only** to `computationally_checked`.
It must never assign `source_verified`, `human_reviewed`, `kitchen_tested`, or `approved`.

## CLI

```bash
# from backend/
python -m recipes.cli quality-audit
python -m recipes.cli quality-audit --json
python -m recipes.cli quality-audit --output backend/recipe_catalog/QUALITY_REPORT.md
python -m recipes.cli quality-audit --recipe-id recipe_oatmeal_banana_001
python -m recipes.cli quality-audit --apply
python -m recipes.cli quality-audit --show-blocking
python -m recipes.cli quality-audit --show-recommendations
python -m recipes.cli quality-audit --show-unverified
```

## Seed catalog honesty

Current 30 seed recipes:

- `creation_method = agent_generated`
- `quality_status = schema_validated` (or `computationally_checked` after `--apply`)
- `source_count = 0`
- not source-verified, not kitchen-tested, not approved

Computational checks do not prove taste, real cook time, storage safety, or market price.

## Limitations

- `ingredient_nutrition` table exists but is empty — macros are snapshot-only
- Pattern evidence is structural / declared, not culinary proof
- Budget evidence is declared `budget_class`, not a verified price
- Fiber patterns require nutrition data (currently insufficient)
- Selector does not filter by quality status yet (`minimum_quality_status` reserved, default `null`)
