# Weekly Planner Readiness Report

**Status:** `ready_for_v1`
**Active recipes:** 86
**Source verified:** 71

## Counts

- Quick: **69**
- Batch-friendly: **46**
- Leftover-friendly: **63**
- Portable: **16**
- Family: **18**
- Fast batch dinner (≤20 + batch + leftover): **6**
- Relations: **155** (recipes without: **4**)

## Fast Batch Dinner Coverage

Recipes where `primary_meal_type=dinner` AND `total_time_minutes≤20` AND `batch_friendly` AND `leftover_friendly`.

- Count: **6**

## Diversity (normalized Shannon)

- Protein: **0.9395**
- Budget: **0.8829**
- Time: **0.7327**

## By primary meal type

- `breakfast`: 23
- `dinner`: 30
- `lunch`: 33

## By meal type membership

- `breakfast`: 26
- `dinner`: 33
- `lunch`: 34

## By protein source

- `beef`: 8
- `chicken`: 14
- `dairy`: 17
- `eggs`: 13
- `fish`: 9
- `legumes`: 13
- `mixed`: 3
- `none`: 3
- `turkey`: 6

## By budget class

- `budget`: 50
- `standard`: 18
- `very_budget`: 18

## By goal (score ≥ 0.6)

- `balanced`: 24
- `budget`: 71
- `family`: 17
- `muscle_gain`: 25
- `quick_cooking`: 65
- `weight_loss`: 65
- `weight_maintenance`: 1

## Per-meal readiness slices

### breakfast

- membership: 26
- quick: 25
- budget/very_budget: 26
- high_protein: 14
- non_poultry: 26
- batch_or_leftover: 7
- vegetarian: 24
- unmet: (none)

### lunch

- membership: 34
- quick: 24
- budget/very_budget: 24
- high_protein: 25
- non_poultry: 23
- batch_or_leftover: 30
- vegetarian: 14
- unmet: (none)

### dinner

- membership: 33
- quick: 26
- budget/very_budget: 25
- high_protein: 24
- non_poultry: 24
- batch_or_leftover: 29
- vegetarian: 15
- unmet: (none)

## Threshold failures

- (none)

## Ready-for-v1 rules

- Active recipes ≥ 60
- Breakfast membership ≥ 20, lunch ≥ 25, dinner ≥ 25
- Source verified ≥ 50
- Per breakfast/lunch/dinner: ≥5 quick, ≥5 budget/very_budget, ≥5 high protein
- Lunch/dinner: ≥4 non-poultry, ≥4 batch|leftover, ≥3 vegetarian
