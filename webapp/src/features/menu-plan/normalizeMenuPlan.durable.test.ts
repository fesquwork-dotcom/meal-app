import { describe, expect, it } from 'vitest';

import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';

const rawPlan = {
  summary: 'План',
  plan_start_date: '2026-07-13',
  strategy_id: 'strategy-1',
  total_cost: 1000,
  days_plan: [
    {
      day: 'День 1',
      meals: [{ type: 'breakfast', recipe_name: 'Овсянка' }],
    },
  ],
  recipes: [],
  basket: [],
};

describe('normalizeMenuPlan durable identity', () => {
  it('keeps a complete durable identity pair', () => {
    const plan = normalizeMenuPlan({
      ...rawPlan,
      menu_plan_id: 'mp-1',
      menu_plan_revision: 3,
    });
    expect(plan?.menu_plan_id).toBe('mp-1');
    expect(plan?.menu_plan_revision).toBe(3);
  });

  it('drops identity without a valid revision', () => {
    for (const revision of [undefined, null, 0, -1, 1.5, 'x']) {
      const plan = normalizeMenuPlan({
        ...rawPlan,
        menu_plan_id: 'mp-1',
        menu_plan_revision: revision,
      });
      expect(plan?.menu_plan_id).toBeUndefined();
      expect(plan?.menu_plan_revision).toBeUndefined();
    }
  });

  it('drops a revision without an id', () => {
    const plan = normalizeMenuPlan({ ...rawPlan, menu_plan_revision: 2 });
    expect(plan?.menu_plan_id).toBeUndefined();
    expect(plan?.menu_plan_revision).toBeUndefined();
  });

  it('treats legacy plans as before', () => {
    const plan = normalizeMenuPlan(rawPlan);
    expect(plan).not.toBeNull();
    expect(plan?.menu_plan_id).toBeUndefined();
    expect(plan?.strategy_id).toBe('strategy-1');
  });

  it('drops blank menu_plan_id strings', () => {
    const plan = normalizeMenuPlan({
      ...rawPlan,
      menu_plan_id: '   ',
      menu_plan_revision: 2,
    });
    expect(plan?.menu_plan_id).toBeUndefined();
  });

  it('preserves catalog generation_engine metadata', () => {
    const plan = normalizeMenuPlan({
      ...rawPlan,
      generation_engine: 'catalog_planner',
      planner_version: '10.12.1',
      planner_score: 12.5,
      planning_duration_ms: 321,
      menu_plan_id: 'mp-1',
      menu_plan_revision: 1,
    });
    expect(plan?.generation_engine).toBe('catalog_planner');
    expect(plan?.planner_version).toBe('10.12.1');
    expect(plan?.planner_score).toBe(12.5);
    expect(plan?.planning_duration_ms).toBe(321);
  });
});
