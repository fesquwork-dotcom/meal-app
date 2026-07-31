import { describe, expect, it } from 'vitest';

import {
  buildHistoryItemViewModel,
  formatHistoryDate,
} from '@/features/menu-history/menuHistoryViewModel';
import type { MenuHistoryItem } from '@/types/menuHistory';

function buildItem(overrides: Partial<MenuHistoryItem> = {}): MenuHistoryItem {
  return {
    menu_plan_id: 'mp-1',
    plan_status: 'superseded',
    created_at: '2026-07-10T10:00:00+00:00',
    plan_start_date: '2026-07-13',
    days: 3,
    total_cost: 2500.4,
    summary: 'План недели',
    has_replacements: false,
    ...overrides,
  };
}

describe('formatHistoryDate', () => {
  it('formats ISO dates in Russian', () => {
    expect(formatHistoryDate('2026-07-13')).toBe('13 июля 2026');
    expect(formatHistoryDate('2026-01-01T10:00:00+00:00')).toBe('1 января 2026');
  });

  it('returns null for malformed input', () => {
    expect(formatHistoryDate(null)).toBeNull();
    expect(formatHistoryDate('июль')).toBeNull();
    expect(formatHistoryDate('2026-13-40')).toBeNull();
  });
});

describe('buildHistoryItemViewModel', () => {
  it('builds a full card view model', () => {
    const viewModel = buildHistoryItemViewModel(buildItem());
    expect(viewModel.title).toBe('План с 13 июля 2026');
    expect(viewModel.statusLabel).toBe('Прошлый план');
    expect(viewModel.isActive).toBe(false);
    expect(viewModel.detailsLine).toBe('3 дня · 2500 ₽');
    expect(viewModel.replacementsNote).toBeNull();
  });

  it('marks the active plan and replacements', () => {
    const viewModel = buildHistoryItemViewModel(
      buildItem({ plan_status: 'active', has_replacements: true }),
    );
    expect(viewModel.statusLabel).toBe('Текущий план');
    expect(viewModel.isActive).toBe(true);
    expect(viewModel.replacementsNote).toBe('Были замены блюд');
  });

  it('degrades gracefully without optional data', () => {
    const viewModel = buildHistoryItemViewModel(
      buildItem({ plan_start_date: null, days: null, total_cost: null, summary: null }),
    );
    expect(viewModel.title).toBe('План недели');
    expect(viewModel.detailsLine).toBeNull();
    expect(viewModel.summary).toBeNull();
  });

  it('pluralizes day counts', () => {
    expect(buildHistoryItemViewModel(buildItem({ days: 1 })).detailsLine).toContain(
      '1 день',
    );
    expect(buildHistoryItemViewModel(buildItem({ days: 5 })).detailsLine).toContain(
      '5 дней',
    );
    expect(buildHistoryItemViewModel(buildItem({ days: 21 })).detailsLine).toContain(
      '21 день',
    );
  });
});
