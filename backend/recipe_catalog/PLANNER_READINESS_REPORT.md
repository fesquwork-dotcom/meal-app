# Weekly Planner Readiness Report

**Status:** `ready_for_v1`
**Active recipes:** 80
**Source verified:** 65

## Counts

- Quick: **63**
- Batch-friendly: **40**
- Leftover-friendly: **57**
- Portable: **16**
- Family: **12**
- Relations: **141** (recipes without: **4**)

## Diversity (normalized Shannon)

- Protein: **0.936**
- Budget: **0.877**
- Time: **0.7591**

## By primary meal type

- `breakfast`: 23
- `dinner`: 24
- `lunch`: 33

## By meal type membership

- `breakfast`: 26
- `dinner`: 27
- `lunch`: 34

## By protein source

- `beef`: 7
- `chicken`: 13
- `dairy`: 17
- `eggs`: 12
- `fish`: 8
- `legumes`: 12
- `mixed`: 3
- `none`: 3
- `turkey`: 5

## By budget class

- `budget`: 47
- `standard`: 16
- `very_budget`: 17

## By goal (score ≥ 0.6)

- `balanced`: 22
- `budget`: 67
- `family`: 13
- `muscle_gain`: 20
- `quick_cooking`: 59
- `weight_loss`: 60
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

- membership: 27
- quick: 20
- budget/very_budget: 21
- high_protein: 19
- non_poultry: 20
- batch_or_leftover: 23
- vegetarian: 13
- unmet: (none)

## Threshold failures

- (none)

## Ready-for-v1 rules

- Active recipes ≥ 60
- Breakfast membership ≥ 20, lunch ≥ 25, dinner ≥ 25
- Source verified ≥ 50
- Per breakfast/lunch/dinner: ≥5 quick, ≥5 budget/very_budget, ≥5 high protein
- Lunch/dinner: ≥4 non-poultry, ≥4 batch|leftover, ≥3 vegetarian
