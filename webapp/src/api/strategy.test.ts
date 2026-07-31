import { describe, expect, it } from 'vitest';

import {
  buildStrategyExplanationViewModel,
  parseStrategyExplanation,
} from '@/features/strategy/buildStrategyExplanationViewModel';
import type { CurrentStrategyResponse } from '@/types/strategy';

function parseCurrentStrategyResponse(input: unknown): CurrentStrategyResponse | null {
  if (input === null || typeof input !== 'object' || Array.isArray(input)) {
    return null;
  }

  const raw = input as Record<string, unknown>;
  const status = raw.status;

  if (status !== 'none' && status !== 'active' && status !== 'completed' && status !== 'superseded') {
    return null;
  }

  return {
    status,
    strategy_id: typeof raw.strategy_id === 'string' ? raw.strategy_id : null,
    plan_start_date: typeof raw.plan_start_date === 'string' ? raw.plan_start_date : null,
    plan_end_date: typeof raw.plan_end_date === 'string' ? raw.plan_end_date : null,
    strategy:
      raw.strategy && typeof raw.strategy === 'object' && !Array.isArray(raw.strategy)
        ? (raw.strategy as CurrentStrategyResponse['strategy'])
        : null,
    explanation: parseStrategyExplanation(raw.explanation),
  };
}

describe('current strategy API response parsing', () => {
  it('parses none response', () => {
    const parsed = parseCurrentStrategyResponse({
      status: 'none',
      strategy_id: null,
      plan_start_date: null,
      plan_end_date: null,
      strategy: null,
    });

    expect(parsed?.status).toBe('none');
    expect(parsed?.strategy).toBeNull();
  });

  it('parses active response', () => {
    const parsed = parseCurrentStrategyResponse({
      status: 'active',
      strategy_id: 'abc',
      plan_start_date: '2026-07-13',
      plan_end_date: '2026-07-15',
      strategy: {
        strategy_version: 1,
        goal: 'home',
        days: 3,
        budget: 3000,
        meal_types: ['breakfast', 'lunch', 'dinner'],
        cook_days: [1, 3],
        shopping_days: [1],
        leftovers_enabled: true,
        repeat_breakfasts: true,
        repeat_lunches: false,
        repeat_dinners: false,
        preferred_proteins: ['any'],
        excluded_products: [],
        cooking_time_limit: 45,
      },
      explanation: {
        version: 1,
        source: 'recorded',
        headline: 'Домашний план на неделю',
        summary: 'Основные блюда готовятся в дни 1 и 3.',
        reasons: [
          {
            code: 'GOAL_HOME',
            title: 'Домашняя еда',
            description: 'Стратегия ориентирована на привычные домашние блюда.',
            category: 'goal',
            priority: 1,
          },
        ],
      },
    });

    expect(parsed?.status).toBe('active');
    expect(parsed?.strategy?.days).toBe(3);
    expect(parsed?.explanation?.headline).toBe('Домашний план на неделю');
  });

  it('parses none response without explanation', () => {
    const parsed = parseCurrentStrategyResponse({
      status: 'none',
      strategy_id: null,
      plan_start_date: null,
      plan_end_date: null,
      strategy: null,
      explanation: null,
    });

    expect(parsed?.explanation).toBeNull();
  });

  it('builds compact view model for week page', () => {
    const viewModel = buildStrategyExplanationViewModel(
      parseCurrentStrategyResponse({
        status: 'active',
        strategy_id: 'abc',
        plan_start_date: '2026-07-13',
        plan_end_date: '2026-07-15',
        strategy: null,
        explanation: {
          version: 1,
          headline: 'Неделя с готовкой три раза',
          summary: 'Основные блюда готовятся в дни 1, 3 и 5.',
          reasons: [
            {
              code: 'COOK_DAYS_REDUCE_DAILY_WORK',
              title: 'Меньше дней готовки',
              description: 'Готовка распределена на дни 1, 3 и 5.',
              category: 'cooking',
              priority: 2,
            },
          ],
        },
      })?.explanation,
    );

    expect(viewModel?.headline).toBe('Неделя с готовкой три раза');
    expect(viewModel?.reasons).toHaveLength(1);
  });

  it('does not break menu when strategy lookup is unavailable', () => {
    const parsed = parseCurrentStrategyResponse({ detail: 'Strategy not found' });
    expect(parsed).toBeNull();
  });
});
