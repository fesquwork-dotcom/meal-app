import { describe, expect, it } from 'vitest';

import { normalizeMenuHistoryPage } from '@/features/menu-history/normalizeMenuHistory';

const validItem = {
  menu_plan_id: 'mp-1',
  plan_status: 'superseded',
  created_at: '2026-07-10T10:00:00+00:00',
  plan_start_date: '2026-07-13',
  days: 3,
  total_cost: 2500,
  summary: 'Сбалансированный план',
  has_replacements: true,
};

describe('normalizeMenuHistoryPage', () => {
  it('keeps valid items and the cursor', () => {
    const page = normalizeMenuHistoryPage({
      items: [validItem],
      next_cursor: '2026-07-10T10:00:00+00:00~mp-1',
    });
    expect(page.items).toHaveLength(1);
    expect(page.items[0].menu_plan_id).toBe('mp-1');
    expect(page.items[0].has_replacements).toBe(true);
    expect(page.next_cursor).toBe('2026-07-10T10:00:00+00:00~mp-1');
  });

  it('returns an empty page for malformed payloads', () => {
    expect(normalizeMenuHistoryPage(null)).toEqual({ items: [], next_cursor: null });
    expect(normalizeMenuHistoryPage('x')).toEqual({ items: [], next_cursor: null });
    expect(normalizeMenuHistoryPage({ items: 'no' })).toEqual({
      items: [],
      next_cursor: null,
    });
  });

  it('drops items without id, status, or created_at', () => {
    const page = normalizeMenuHistoryPage({
      items: [
        { ...validItem, menu_plan_id: '' },
        { ...validItem, plan_status: 'draft' },
        { ...validItem, created_at: null },
        validItem,
      ],
      next_cursor: null,
    });
    expect(page.items).toHaveLength(1);
  });

  it('nullifies invalid optional fields instead of dropping the item', () => {
    const page = normalizeMenuHistoryPage({
      items: [
        {
          ...validItem,
          days: -1,
          total_cost: Number.NaN,
          summary: '',
          plan_start_date: 42,
          has_replacements: 'yes',
        },
      ],
      next_cursor: null,
    });
    const item = page.items[0];
    expect(item.days).toBeNull();
    expect(item.total_cost).toBeNull();
    expect(item.summary).toBeNull();
    expect(item.plan_start_date).toBeNull();
    expect(item.has_replacements).toBe(false);
  });

  it('caps the page size', () => {
    const page = normalizeMenuHistoryPage({
      items: Array.from({ length: 30 }, (_item, index) => ({
        ...validItem,
        menu_plan_id: `mp-${index}`,
      })),
      next_cursor: null,
    });
    expect(page.items).toHaveLength(20);
  });
});
