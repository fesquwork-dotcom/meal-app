import { describe, expect, it } from 'vitest';

import { buildPlanDeltaViewModel } from '@/features/menu-history/planDeltaViewModel';
import type { PlanDeltaMetric, PlanDeltaResult } from '@/types/planDelta';

function metric(overrides: Partial<PlanDeltaMetric>): PlanDeltaMetric {
  return {
    id: 'total_cost',
    status: 'available',
    unit: 'rub',
    original: 2700,
    current: 2450,
    delta: -250,
    direction: 'decreased',
    ...overrides,
  };
}

function result(
  metrics: PlanDeltaMetric[],
  hasReplacements = true,
): PlanDeltaResult {
  return {
    menu_plan_id: 'mp-1',
    revision: 2,
    has_replacements: hasReplacements,
    delta: { version: 1, metrics },
  };
}

describe('buildPlanDeltaViewModel', () => {
  it('formats a cost decrease as original → current with a signed change', () => {
    const viewModel = buildPlanDeltaViewModel(result([metric({})]));
    expect(viewModel?.title).toBe('Изменения после замен');
    expect(viewModel?.lines[0].label).toBe('Стоимость плана');
    expect(viewModel?.lines[0].valueLine).toBe('2700 ₽ → 2450 ₽');
    expect(viewModel?.lines[0].changeLabel).toBe('−250 ₽');
    expect(viewModel?.hasChanges).toBe(true);
  });

  it('formats increases with a plus sign', () => {
    const viewModel = buildPlanDeltaViewModel(
      result([metric({ current: 3130, delta: 430, direction: 'increased' })]),
    );
    expect(viewModel?.lines[0].changeLabel).toBe('+430 ₽');
  });

  it('shows changed meals as a plain count', () => {
    const viewModel = buildPlanDeltaViewModel(
      result([
        metric({
          id: 'changed_meals',
          unit: 'count',
          original: null,
          current: null,
          delta: 2,
          direction: 'increased',
        }),
      ]),
    );
    expect(viewModel?.lines[0].label).toBe('Заменено блюд');
    expect(viewModel?.lines[0].valueLine).toBe('2');
    expect(viewModel?.lines[0].changeLabel).toBeNull();
  });

  it('hides unavailable metrics entirely', () => {
    const viewModel = buildPlanDeltaViewModel(
      result([
        metric({}),
        metric({ id: 'calories', status: 'unavailable', delta: null, direction: null }),
      ]),
    );
    expect(viewModel?.lines).toHaveLength(1);
  });

  it('returns null without replacements or without visible lines', () => {
    expect(buildPlanDeltaViewModel(result([metric({})], false))).toBeNull();
    expect(
      buildPlanDeltaViewModel(
        result([metric({ status: 'unavailable', delta: null, direction: null })]),
      ),
    ).toBeNull();
    expect(buildPlanDeltaViewModel(null)).toBeNull();
  });

  it('marks unchanged plans without change labels', () => {
    const viewModel = buildPlanDeltaViewModel(
      result([
        metric({ current: 2700, delta: 0, direction: 'unchanged' }),
        metric({
          id: 'changed_meals',
          unit: 'count',
          original: null,
          current: null,
          delta: 0,
          direction: 'unchanged',
        }),
      ]),
    );
    expect(viewModel?.lines[0].changeLabel).toBeNull();
    expect(viewModel?.hasChanges).toBe(false);
  });

  it('formats minutes and grams units', () => {
    const viewModel = buildPlanDeltaViewModel(
      result([
        metric({
          id: 'cooking_time_minutes',
          unit: 'minutes',
          original: 90,
          current: 60,
          delta: -30,
          direction: 'decreased',
        }),
        metric({
          id: 'protein_grams',
          unit: 'grams',
          original: 120,
          current: 140,
          delta: 20,
          direction: 'increased',
        }),
      ]),
    );
    expect(viewModel?.lines[0].valueLine).toBe('90 мин → 60 мин');
    expect(viewModel?.lines[0].changeLabel).toBe('−30 мин');
    expect(viewModel?.lines[1].changeLabel).toBe('+20 г');
  });
});
