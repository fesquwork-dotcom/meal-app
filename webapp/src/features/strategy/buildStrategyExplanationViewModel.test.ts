import { describe, expect, it } from 'vitest';

import {
  buildStrategyExplanationViewModel,
  parseStrategyExplanation,
} from '@/features/strategy/buildStrategyExplanationViewModel';

const sampleExplanation = {
  version: 1,
  source: 'recorded' as const,
  headline: 'Неделя с готовкой три раза',
  summary: 'Основные блюда готовятся в дни 1, 3 и 5.',
  reasons: [
    {
      code: 'COOK_DAYS_REDUCE_DAILY_WORK',
      title: 'Меньше дней готовки',
      description: 'Готовка распределена на дни 1, 3 и 5.',
      category: 'cooking',
      priority: 2,
      related_days: [1, 3, 5],
    },
    {
      code: 'GOAL_BUDGET',
      title: 'Экономный подход',
      description: 'Стратегия отдаёт приоритет стоимости.',
      category: 'goal',
      priority: 1,
    },
    {
      code: 'LEFTOVERS_REDUCE_COOKING',
      title: 'Переиспользование заготовок',
      description: 'Часть блюд используется повторно.',
      category: 'leftovers',
      priority: 3,
    },
    {
      code: 'BUDGET_LIMITED_VARIETY',
      title: 'Ориентир по бюджету',
      description: 'Меню построено в пределах ориентировочного бюджета.',
      category: 'budget',
      priority: 4,
    },
    {
      code: 'COOKING_TIME_LIMIT_MEDIUM',
      title: 'Средняя длительность готовки',
      description: 'План рассчитан на блюда до 45 минут.',
      category: 'time',
      priority: 5,
    },
    {
      code: 'EXCLUSIONS_APPLIED',
      title: 'Исключения учтены',
      description: 'Исключённые продукты учтены во всех рецептах и корзине.',
      category: 'exclusions',
      priority: 10,
    },
  ],
};

describe('strategy explanation parsing', () => {
  it('parses explanation response', () => {
    const parsed = parseStrategyExplanation(sampleExplanation);
    expect(parsed?.headline).toBe('Неделя с готовкой три раза');
    expect(parsed?.reasons).toHaveLength(6);
  });

  it('returns null for missing explanation', () => {
    expect(parseStrategyExplanation(null)).toBeNull();
    expect(parseStrategyExplanation({})).toBeNull();
  });

  it('limits visible reasons to five while preserving order', () => {
    const viewModel = buildStrategyExplanationViewModel(parseStrategyExplanation(sampleExplanation));
    expect(viewModel?.reasons).toHaveLength(5);
    expect(viewModel?.reasons[0].code).toBe('GOAL_BUDGET');
    expect(viewModel?.reasons[4].code).toBe('COOKING_TIME_LIMIT_MEDIUM');
  });

  it('does not expose raw reason codes as user-facing text in view model titles', () => {
    const viewModel = buildStrategyExplanationViewModel(parseStrategyExplanation(sampleExplanation));
    for (const reason of viewModel?.reasons ?? []) {
      expect(reason.title).not.toBe(reason.code);
    }
  });
});

describe('strategy explanation graceful fallback', () => {
  it('returns null view model when explanation is missing', () => {
    expect(buildStrategyExplanationViewModel(null)).toBeNull();
  });
});
