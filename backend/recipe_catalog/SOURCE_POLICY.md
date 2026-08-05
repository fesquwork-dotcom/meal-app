# Recipe Source Policy (Sprint 10.8)

This document defines how culinary sources are collected, compared, and attached to catalog recipes.

## Purpose

Catalog recipes must not be treated as trusted solely because an LLM or agent produced a plausible dish. Source verification creates a traceable chain:

```
catalog gap → recipe concept → real sources → source comparison
→ normalized internal recipe → provenance → quality checks
→ catalog import → selector → evaluation
```

## Allowed source types

1. Reputable culinary websites (e.g. established recipe publishers)
2. Cookbooks (title, author, edition/page when available)
3. Manufacturer cooking instructions (packaging, official brand pages)
4. Official food / nutrition databases
5. Established culinary publications (magazines, extension services)
6. Internal kitchen tests
7. Human expert review

Mapped to `SourceType`:

| Policy category | Enum value |
|-----------------|------------|
| Culinary website | `culinary_website` |
| Cookbook | `cookbook` |
| Manufacturer instruction | `manufacturer_instruction` |
| Nutrition database | `nutrition_database` |
| Human expert | `human_expert` |
| Internal kitchen test | `internal_test` |
| Other established publication | `other` (with notes) |

## Not independent sources

Do **not** record as culinary sources:

- LLM / agent responses
- Search snippets without opening the underlying page
- Auto-generated text without a human-traceable publisher
- Aggregators that do not disclose origin
- Dish names alone
- Existing seed YAML without external references
- Placeholder URLs (`example.com`, `n/a`, empty references)

## Minimum source requirements

| Case | Minimum |
|------|---------|
| Source-backed catalog import (`ready_for_catalog_import`) | **2 independent sources** |
| Simple technological fact (e.g. manufacturer cook time for a grain) | 1 authoritative source may suffice for that fact |
| Promotion to `source_verified` via Quality Gate | Prefer ≥2 real `recipe_sources`; computational checks must pass |

Independence means different publishers/domains or different primary works (not two mirrors of the same article).

## What to extract from sources

Extract **facts**, not prose:

- Ingredients (canonicalized)
- Approximate proportions / quantities
- Cooking method
- Temperature (when stated)
- Prep / cook / total time
- Yield / servings
- Storage guidance (when stated)

Do **not** copy wholesale:

- Introductions, marketing copy, author tips
- Long verbatim instruction sequences
- Copyrighted narrative text

Internal steps must be rewritten briefly in the catalog’s own voice. Keep `source_reference` for provenance.

## Source comparison

Use deterministic comparison (`RecipeSourceComparison`) over structured `RecipeSourceObservation` records.

If automatic extraction from the web is unavailable:

1. Do **not** invent observations
2. Enter **manual structured observations** from sources the operator actually opened
3. Leave unresolved questions explicit

## Quality status after source workflow

After successful source-backed import and Quality Gate (no blocking errors, sources present):

- Maximum automatic status: **`source_verified`**
- Never auto-assign: `human_reviewed`, `kitchen_tested`, `approved`

`creation_method` for new source-backed recipes: **`source_adapted`**.

Existing agent-generated seeds may receive `recipe_sources` and a source review without automatic ingredient/time rewrites. Significant divergence yields `RECIPE_SOURCE_MISMATCH` recommendations only.

## Honesty rule

If real sources cannot be obtained, keep concepts as pending research. Do not fabricate URLs, publishers, nutrition numbers, or verification outcomes.
