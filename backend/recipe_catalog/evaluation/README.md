# Catalog Evaluation Scenarios

Версионируемые сценарии для `python -m recipes.cli evaluate`.

## Files

- `baseline_scenarios.yaml` — baseline meal types + goal scenarios
- `restrictive_scenarios.yaml` — time, budget, protein, combined, stress

Перегенерация:

```bash
cd backend
python recipes/evaluation/generate_scenarios.py
```

## Adding a scenario

```yaml
- id: unique_slug
  name: Human readable name
  description: Why this matters
  scenario_group: combined   # baseline|goal|budget|time|protein|...
  expected_min_candidates: 5
  weight: 1.0
  enabled: true
  context:
    meal_type: dinner
    goal: weight_loss
    max_total_time_minutes: 30
    limit: 10
```

Rules:

- `id` must be unique across all files
- `context` uses `CandidateSelectionContext` fields
- stress scenarios should use `weight: 0.25` and low/zero expected
- do not put evaluation data in SQLite
