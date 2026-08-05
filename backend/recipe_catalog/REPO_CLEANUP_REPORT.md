# Sprint 10.11.3 — Repository Cleanup & Git Hygiene

## Audit

| Category | Decision | Items |
|--|--|--|
| One-off sprint helpers | **REMOVE** | `append_relations_10_9.py`, `attach_source_review_10_9.py`, `generate_sprint_10_9.py` |
| Generated diagnostics JSON / dumps | **REMOVE** | `DIAGNOSE_PLAN_COOK_DAY.json`, `USER_116057789_*.json`, `_cli_family_diag.json`, `_no_plan_sweep.json`, `_diagnose_stderr.txt`, one-off profile snapshots |
| Markdown reports | **KEEP** | `*_REPORT.md`, `QUALITY_WORKFLOW.md`, `SOURCE_POLICY.md`, `REJECTED_DUPLICATES_10_9.md` |
| Catalog / evaluation | **KEEP** | recipes YAML, relations, ingredients, `evaluation/*`, `BASELINE_SPRINT_10_9.json` |
| Tests / production code | **KEEP** | Planner, Selector, Catalog, API, `test_*.py` |

## Removed

- `backend/append_relations_10_9.py`
- `backend/attach_source_review_10_9.py`
- `backend/generate_sprint_10_9.py`
- `backend/recipe_catalog/DIAGNOSE_PLAN_COOK_DAY.json`
- `backend/recipe_catalog/USER_116057789_COOK_DAY_DIAGNOSTICS.json`
- `backend/recipe_catalog/USER_116057789_DIAGNOSTICS.json`
- `backend/recipe_catalog/_cli_family_diag.json`
- `backend/recipe_catalog/_no_plan_sweep.json`
- `backend/recipe_catalog/_diagnose_stderr.txt`
- `backend/recipe_catalog/no_plan_profile.json`
- `backend/recipe_catalog/user42_like_profile.json`
- `backend/recipe_catalog/user42_profile.json`

## Kept (docs / catalog)

- All `*_REPORT.md` under `recipe_catalog/` (+ evaluation)
- Recipe YAML, relations, ingredients, quality workflow
- `evaluation/BASELINE_SPRINT_10_9.json` and scenario YAMLs

## .gitignore additions

Section **Diagnostics / Temporary**:

- `DIAGNOSE_*.json`, `*_diagnostics.json`
- `*_stderr.txt`, `*_stdout.txt`
- `planner_dump*`, `*_diag.json`, `*_sweep.json`
- `*.tmp`, `*.orig`, `*.rej`
- `artifacts/`, `backend/tmp/`, `backend/artifacts/`

(`tmp/` / `temp/` already ignored.)

## CLI hygiene

`diagnose-plan --output PATH` writes JSON diagnostics; bare filenames redirect under `tmp/` so dumps stay out of `recipe_catalog/`.

## Reference check

No remaining imports/refs to removed helpers or diagnostic dumps (only this report).

## Backend suite

`1487 passed` (unchanged).
