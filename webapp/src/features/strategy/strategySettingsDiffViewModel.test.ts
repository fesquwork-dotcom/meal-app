import { describe, expect, it } from 'vitest';

import {
  buildStrategySettingsDiffViewModel,
  formatSettingChangeLine,
} from '@/features/strategy/strategySettingsDiffViewModel';
import type { StrategySettingsDiff } from '@/types/strategyCompare';

function diff(overrides: Partial<StrategySettingsDiff> = {}): StrategySettingsDiff {
  return {
    version: 1,
    has_changes: true,
    changes: [
      {
        key: 'cooking_time_limit',
        category: 'cooking',
        change_type: 'changed',
        title: 'Максимальное время активной готовки',
        description: 'Максимальное время активной готовки: до 45 минут → до 90 минут.',
        current: { display_value: 'до 45 минут' },
        next: { display_value: 'до 90 минут' },
        priority: 7,
      },
    ],
    unchanged_count: 7,
    comparison_quality: 'exact',
    ...overrides,
  };
}

describe('strategy settings diff view model', () => {
  it('builds changed diff block', () => {
    const viewModel = buildStrategySettingsDiffViewModel(diff());
    expect(viewModel?.title).toBe('Что изменится в следующем плане');
    expect(viewModel?.changes).toHaveLength(1);
    expect(viewModel?.unchangedLine).toContain('7');
  });

  it('handles no changes', () => {
    const viewModel = buildStrategySettingsDiffViewModel(
      diff({ has_changes: false, changes: [], unchanged_count: 14 }),
    );
    expect(viewModel?.noChanges).toBe(true);
    expect(viewModel?.title).toContain('тем же основным правилам');
  });

  it('shows partial notice', () => {
    const viewModel = buildStrategySettingsDiffViewModel(
      diff({ comparison_quality: 'partial' }),
    );
    expect(viewModel?.partialNotice).toContain('частичное сравнение');
  });

  it('formats scalar change line', () => {
    const line = formatSettingChangeLine(diff().changes[0]);
    expect(line).toContain('45');
    expect(line).toContain('90');
  });

  it('uses description for source-only change', () => {
    const line = formatSettingChangeLine({
      key: 'prefer_faster_meals_source',
      category: 'cooking',
      change_type: 'source_changed',
      title: 'Источник',
      description: 'Предпочтение быстрых блюд теперь задано в профиле.',
      current: { display_value: 'по истории замен', source: 'memory' },
      next: { display_value: 'задано в профиле', source: 'profile' },
      priority: 15,
    });
    expect(line).toContain('профиле');
  });
});
