# Day4 Leftover Deadlock — Production Investigation

Diagnostics-only follow-up (no Planner/weights/catalog/`max_extra_cook_days` changes).

## Reproduction matrix

| Setup | Strict | Relaxed |
|--|--|--|
| `days=5`, `cook_days=[1,3,5]`, CTL=45, budget≥1500 | SUCCESS | SUCCESS |
| Same, CTL=**20** (natural) | PARTIAL `COOK_DAY_CONFLICT` @ `day2_dinner` | PARTIAL @ **`day4_dinner`** |
| `cook_days=[1,5]`, CTL=45 | PARTIAL @ day3 | PARTIAL @ `day4_lunch` |

Artifacts: `backend/tmp/day4_ctl20_investigation.json`, `backend/tmp/day4_leftover_investigation.json`.

## Natural failure (CTL=20) — answers 1–13

### 1. Partial plan (day1 → day4_lunch)

| Slot | Recipe | leftover | notes |
|--|--|--|--|
| day1_breakfast | savory_cottage_cucumber | N | |
| day1_lunch | pasta_peas_cheese_lunch | N | batch+lo → cooked=2 |
| day1_dinner | tuna_zucchini_dinner | N | lo_f only, **not batch** → cooked=1 |
| day2_breakfast | chickpea_yogurt_bowl_flex | N | |
| day2_lunch | pasta_peas_cheese_lunch | **Y** ← day1_lunch | |
| day2_dinner | omelet_tomato_cheese | N | **COOK_DAY_MISS** (extra day=2) |
| day3_breakfast | millet_milk_porridge | N | breakfast → cooked=1 |
| day3_lunch | chickpea_couscous_lunch | N | batch+lo → cooked=2 |
| day3_dinner | pasta_tuna_tomato | N | **neither** batch nor lo_f → cooked=1 |
| day4_breakfast | cottage_berries_bowl | N | |
| day4_lunch | chickpea_couscous_lunch | **Y** ← day3_lunch | |

### 2–3. Cooking instances

Lunch batch instances produced the only leftovers. By `day4_dinner` every instance has `remaining=0`. Dinner cooks never reserved leftover servings.

### 4. Leftover assignments

- `day2_lunch` ← `day1_lunch`
- `day4_lunch` ← `day3_lunch`
- **No dinner leftovers at all**

### 5–8. `day4_dinner` actions

- Reconstructed `_actions_for_slot`: **0 surviving actions**
- **No leftover actions** — all instances `remaining<=0` (nothing to reject)
- Cook candidates after hard filters: 4 → all rejected:
  - `RECIPE_REPEAT` (already cooked)
  - `MAX_EXTRA_COOK_DAYS` (`day=4 extra=[2] max=1`)

### 9. day3 pool (CTL=20)

- Lunch pick: batch+leftover (covers day4_lunch only)
- Dinner pool under CTL=20: **0** batch+leftover dinner candidates (time filter removed e.g. `egg_tomato_skillet`)

### 10. Alternate day3 dinner?

**No** under CTL=20 — no unused batch+leftover dinner in the surviving pool.  
Under CTL=45 success path, day3_dinner=`egg_tomato_skillet` (batch+lo) **does** feed `day4_dinner`.

### 11. Leftover consumption limit

`WeeklyPlannerConfig.max_leftovers_per_cook = 1`

### 12. Multi-slot coverage from one cook?

**No.** Batch cook sets `servings_cooked = 1 + max_leftovers_per_cook` → **exactly one** future leftover meal.

### 13. Beam look-ahead for future non-cook leftovers?

**No.** `WeeklyPlanScorer` only scores **already assigned** meals; `batch_efficiency` is a local retrospective bonus (`leftovers + 0.5 * batch_cooks`) / days — no projection of upcoming non-cook slots.

## 14. Diagnostics fix (done)

`infer_termination_reason` previously ignored `MAX_EXTRA_COOK_DAYS` weekly removals and fell through to hard-filter `TIME_LIMIT` / `BUDGET_LIMIT`.

Now returns `TerminationReason.MAX_EXTRA_COOK_DAYS` when weekly wipe is dominated by that code (even if earlier hard filters also removed TIME/BUDGET candidates).

## Root cause

With alternating cook days (`1,3,5`), non-cook days (2,4) need leftovers **or** the single allowed extra cook day.

Failure chain under tight time:

1. Day1 dinner not batch → no dinner leftover for day2.
2. Relaxed pass spends `max_extra_cook_days=1` on **day2_dinner**.
3. Day3 dinner not batch+lo (or none available under CTL) → no dinner leftover for day4.
4. Day4 lunch consumes the only day3 lunch leftover.
5. **day4_dinner**: no leftover remaining + cannot cook (`MAX_EXTRA_COOK_DAYS`).

Structural fragility: `max_leftovers_per_cook=1` + no look-ahead + one extra cook day.

## Minimal fix options (NOT implemented — investigation only)

Prefer smallest change that preserves architecture:

1. **Config (smallest):** raise `max_leftovers_per_cook` from 1 → 2 so one batch dinner can cover two future leftover meals when needed — still no Planner algorithm rewrite.
2. **Soft preference (scoring only):** increase weight/bonus for choosing `batch_friendly ∧ leftover_friendly` on cook days that precede a non-cook day (requires weight/scoring change — out of scope for this investigation).
3. **Catalog/time:** ensure enough quick batch+leftover dinners survive medium/fast cooktime pools (catalog/CTL — out of scope).

Recommended first production fix candidate: **(1)** `max_leftovers_per_cook=2` behind a config flag, with tests for `cook_days=[1,3,5]` under CTL=20 / sparse leftovers.
