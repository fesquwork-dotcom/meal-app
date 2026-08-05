# Planner Diagnostics — Sprint 10.11.1

**Goal:** Explain `NO_PLAN` / `PARTIAL` failures with structured diagnostics without changing beam search decisions, weights, candidate pools, scoring, or hard-filter outcomes.

---

## Problem

`CatalogMenuGenerationService` raised `CatalogGenerationError(PLANNER_NO_PLAN|PLANNER_PARTIAL_PLAN)` with thin `weekly_plan.diagnostics` (expanded / pruned / filter causes / unfilled only). Operators could not see which slot failed, why candidates were rejected, or whether the stop was cook-day / leftovers / quality / max_states.

Root causes in `recipes/planning/planner.py`:

1. `next_beam` empty after a slot → immediate NO_PLAN / PARTIAL finalize
2. `max_states` cutoff → search stops with incomplete assignments

---

## Changes

| Area | Change |
|------|--------|
| `recipes/planning/diagnostics.py` | **NEW** — `TerminationReason`, `RejectedCandidate`, `SlotDiagnostics`, `PlannerDiagnostics`, `infer_termination_reason` |
| `recipes/planning/models.py` | `PlanDiagnostics = PlannerDiagnostics` alias; `WeeklyRecipePlan.diagnostics` typed as `PlannerDiagnostics` |
| `recipes/planning/planner.py` | Instrument only: `_actions_for_slot` returns `(actions, SlotActionStats)`; beam metrics; slot diags; termination inference; `planner_failed` log |
| `menu_generation/catalog_service.py` | `details.planner_diagnostics` (+ legacy `diagnostics`); `planner_failed` log |
| `main.py` | `catalog_generation_error_handler` passes `details=exc.details` |
| `generation_jobs/*` + `database.py` | Optional `error_details_json` column; `mark_failed(..., error_details=)`; API `error_details` |
| `recipes/cli.py` | `diagnose-plan` command |
| `tests/test_planner_diagnostics.py` | Success / failure / CatalogGenerationError / serialization / CLI smoke |

---

## TerminationReason mapping

| Reason | When inferred |
|--------|----------------|
| `SUCCESS` | Full plan filled |
| `NO_CANDIDATES` | Failed slot `after_hard_filters == 0` (non-quality) |
| `QUALITY_LIMIT` | Hard survivors wiped mainly by quality / quality dominates empty hard pool |
| `COOK_DAY_CONFLICT` | Weekly removals dominated by `COOK_DAY_REQUIRED` → mapped `COOK_DAY_CONFLICT` |
| `LEFTOVER_CHAIN_FAILED` | Non-cook day + leftover-related weekly removals dominate |
| `TIME_LIMIT` | Time codes dominate weekly or hard removals |
| `BUDGET_LIMIT` | Budget codes dominate |
| `CONSTRAINT_CONFLICT` | Hard survivors exist but weekly constraints wipe all actions |
| `MAX_STATES` | `max_states` hit before completion |
| `BEAM_EXHAUSTED` | Empty beam / no actions without a clearer dominant cause |
| `UNKNOWN` | Fallback |

---

## Diagnostics shape (sample)

```json
{
  "planning_status": "no_plan",
  "termination_reason": "NO_CANDIDATES",
  "failed_slot": "day1_breakfast",
  "last_successful_slot": null,
  "states_expanded": 0,
  "expanded_states": 0,
  "visited_states": 1,
  "beam_iterations": 1,
  "slots_total": 21,
  "slots_completed": 0,
  "hard_filter_stats": {
    "TIME_LIMIT_EXCEEDED": 40,
    "EXCLUDED_PROTEIN_SOURCE": 30,
    "QUALITY_BELOW_MINIMUM": 5
  },
  "constraint_statistics": {},
  "beam_metrics": {
    "beam_width": 8,
    "iterations": 1,
    "max_queue": 1,
    "visited": 1,
    "expanded": 0,
    "pruned": 1,
    "final_queue_size": 1,
    "max_states_hit": false
  },
  "search_complexity": {
    "candidate_evaluations": 0,
    "constraint_evaluations": 0,
    "ranking_evaluations": 0,
    "planning_duration_ms": 12.3
  },
  "partial_plan": {
    "score": null,
    "assignments": []
  },
  "slots": [
    {
      "slot_id": "day1_breakfast",
      "meal_type": "breakfast",
      "filled": false,
      "candidate_count_before_filters": 80,
      "candidate_count_after_hard_filters": 0,
      "candidate_count_after_weekly_constraints": 0,
      "hard_filter_removals": {"TIME_LIMIT_EXCEEDED": 40},
      "best_failed_candidates": []
    }
  ],
  "unfilled_slots": ["day1_breakfast", "..."],
  "slot_filter_causes": {"day1_breakfast": {"TIME_LIMIT_EXCEEDED": 40}}
}
```

Legacy fields (`states_expanded`, `states_pruned`, `candidate_pool_size`, `beam_width`, `planning_duration_ms`, `unfilled_slots`, `slot_filter_causes`, `warnings`) remain populated.

---

## Unchanged (critical)

- `WeeklyPlannerWeights` / `DEFAULT_WEEKLY_WEIGHTS`
- `WeeklyPlannerConfig` defaults: `beam_width=8`, `candidate_pool_size=15`, `max_states=4000`
- Selector weights / hard-filter logic outcomes
- Catalog contents
- Action list order from `_actions_for_slot` (same accept/reject decisions; stats are side-channel only)

---

## API / jobs

- Sync errors: `details` includes full `planner_diagnostics` for clients (frontend may ignore).
- Async jobs: `error_details_json` persisted; `GenerationJobStatusResponse.error_details` optional.

## CLI

```bash
python -m recipes.cli diagnose-plan --days 7 --goal balanced --budget standard --max-time 45 [--leftovers] [--cook-days 1,3,5] [--source-verified-only] [--json] [--db PATH]
```

---

## Tests

`tests/test_planner_diagnostics.py` covers success diagnostics, impossible-constraint failure path, `CatalogGenerationError.details`, `to_dict` serialization, and CLI smoke.
