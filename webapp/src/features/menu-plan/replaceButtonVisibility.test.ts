import { readFileSync, readdirSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import {
  canReplaceMeal,
  explainReplaceMealAvailability,
} from '@/features/menu-plan/canReplaceMeal';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import { wrapForStorage, unwrapFromStorage } from '@/lib/storageVersion';
import type { MenuPlan } from '@/types/menu';

// Plan is active on Jul 14–16, 2026 (3 days starting Jul 14).
const ACTIVE_NOW = new Date(2026, 6, 15, 12, 0, 0);
const AFTER_COMPLETION = new Date(2026, 6, 17, 0, 30, 0);

function buildPlan(overrides: Partial<MenuPlan> = {}): MenuPlan {
  return {
    summary: 'План',
    plan_start_date: '2026-07-14',
    strategy_id: 'strategy-123',
    total_cost: 1000,
    days_plan: [1, 2, 3].map((day) => ({
      day: `День ${day}`,
      breakfast: '',
      lunch: '',
      dinner: `Ужин ${day}`,
      meals: [
        {
          type: 'dinner',
          recipe_name: `Ужин ${day}`,
          meal_id: `day${day}_dinner`,
          requires_cooking: true,
          prepared_on_day: day,
          uses_leftovers: false,
        },
      ],
    })),
    recipes: [
      {
        name: 'Ужин 1',
        emoji: '🍲',
        cook_time: '30 мин',
        kbju: '',
        ingredients: [{ name: 'овощи', amount: '300 г' }],
        steps: ['Готовить'],
      },
    ],
    basket: [{ category: 'Овощи', items: [{ name: 'овощи', weight: '300 г', price: 200 }] }],
    ...overrides,
  };
}

describe('replace button visibility regression', () => {
  it('active current plan → Replace available', () => {
    const plan = buildPlan();
    expect(canReplaceMeal(plan, ACTIVE_NOW)).toBe(true);
    const explanation = explainReplaceMealAvailability(plan, ACTIVE_NOW);
    expect(explanation.reasons).toEqual({
      hasPlan: true,
      hasStrategyId: true,
      planStartDate: '2026-07-14',
      planLength: 3,
      planDayStateKind: 'active',
    });
  });

  it('reload (storage + normalize round-trip) → Replace still available', () => {
    const stored = wrapForStorage(buildPlan());
    const loaded = unwrapFromStorage<MenuPlan>(stored);
    const normalized = normalizeMenuPlan(loaded);
    expect(normalized?.strategy_id).toBe('strategy-123');
    expect(normalized?.plan_start_date).toBe('2026-07-14');
    expect(canReplaceMeal(normalized, ACTIVE_NOW)).toBe(true);
  });

  it('replacement success payload (normalized server response) → Replace remains', () => {
    // Simulates ReplaceMealResponse.menu_plan going through the same normalizer
    // as api/replaceMeal.ts before coordinateReplacementSuccess.
    const serverPlan = {
      ...buildPlan(),
      menu_plan_id: 'mp-1',
      menu_plan_revision: 2,
    };
    const normalized = normalizeMenuPlan(serverPlan);
    expect(normalized?.menu_plan_id).toBe('mp-1');
    expect(canReplaceMeal(normalized, ACTIVE_NOW)).toBe(true);
  });

  it('replacement 422 (REPLACEMENT_PRICE_UNRESOLVED) → plan untouched, Replace remains', () => {
    const plan = buildPlan();
    const before = structuredClone(plan);
    const error = classifyStrategyWorkflowError(
      new AxiosError('request failed', undefined, undefined, undefined, {
        data: { code: 'REPLACEMENT_PRICE_UNRESOLVED', message: 'x' },
        status: 422,
        statusText: 'Error',
        headers: {},
        config: { headers: new AxiosHeaders() },
      }),
    );
    expect(error.code).toBe('REPLACEMENT_PRICE_UNRESOLVED');
    expect(plan).toEqual(before);
    expect(canReplaceMeal(plan, ACTIVE_NOW)).toBe(true);
  });

  it('completed plan (calendar passed) → Replace hidden with completed reason', () => {
    const plan = buildPlan();
    expect(canReplaceMeal(plan, AFTER_COMPLETION)).toBe(false);
    expect(explainReplaceMealAvailability(plan, AFTER_COMPLETION).reasons.planDayStateKind).toBe(
      'completed',
    );

    // One-day plan generated "yesterday evening" hides the button after midnight.
    const oneDay = buildPlan({
      plan_start_date: '2026-07-16',
      days_plan: buildPlan().days_plan.slice(0, 1),
    });
    expect(canReplaceMeal(oneDay, new Date(2026, 6, 16, 23, 0, 0))).toBe(true);
    expect(canReplaceMeal(oneDay, new Date(2026, 6, 17, 0, 41, 0))).toBe(false);
  });

  it('plan without strategy_id (legacy/history payload) → Replace hidden', () => {
    const plan = buildPlan({ strategy_id: undefined });
    expect(canReplaceMeal(plan, ACTIVE_NOW)).toBe(false);
    expect(explainReplaceMealAvailability(plan, ACTIVE_NOW).reasons.hasStrategyId).toBe(false);
  });

  it('history pages never wire the replacement handler', () => {
    // DayPlanCard renders the button only when onRequestMealReplacement is
    // passed; only WeekPage and HomePage may pass it, and both gate it with
    // canReplaceMeal. History pages must not import the replace wiring.
    for (const page of ['pages/WeekPage.tsx', 'pages/HomePage.tsx']) {
      const source = readFileSync(resolve(__dirname, '../../', page), 'utf-8');
      expect(source).toContain('canReplaceMeal');
      expect(source).toContain('onRequestMealReplacement');
    }

    let historyCombined = '';
    const walk = (path: string) => {
      for (const entry of readdirSync(path)) {
        const full = resolve(path, entry);
        if (statSync(full).isDirectory()) {
          walk(full);
        } else if (/\.(ts|tsx)$/.test(entry) && !entry.includes('.test.')) {
          historyCombined += readFileSync(full, 'utf-8');
        }
      }
    };
    walk(resolve(__dirname, '../../', 'features/menu-history'));
    expect(historyCombined.length).toBeGreaterThan(0);
    expect(historyCombined).not.toContain('onRequestMealReplacement');
    expect(historyCombined).not.toContain('ReplaceMealSheet');
  });
});
