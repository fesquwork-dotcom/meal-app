import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getMenuHistory,
  getMenuPlanDetail,
  getMenuPlanOriginal,
} from '@/api/menuHistory';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from '@/api/client';

const planPayload = {
  summary: 'План',
  plan_start_date: '2026-07-13',
  total_cost: 500,
  days_plan: [
    {
      day: 'День 1',
      meals: [{ type: 'breakfast', recipe_name: 'Овсянка' }],
    },
  ],
  recipes: [],
  basket: [],
};

describe('menu history API client', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
  });

  it('loads and normalizes a history page with cursor', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        items: [
          {
            menu_plan_id: 'mp-1',
            plan_status: 'active',
            created_at: '2026-07-10T10:00:00+00:00',
            plan_start_date: '2026-07-13',
            days: 3,
            total_cost: 500,
            summary: 'План',
            has_replacements: false,
          },
        ],
        next_cursor: 'cursor-1',
      },
    });

    const page = await getMenuHistory();
    expect(api.get).toHaveBeenCalledWith('/api/menu/history', { params: undefined });
    expect(page.items).toHaveLength(1);
    expect(page.next_cursor).toBe('cursor-1');

    await getMenuHistory('cursor-1');
    expect(api.get).toHaveBeenLastCalledWith('/api/menu/history', {
      params: { cursor: 'cursor-1' },
    });
  });

  it('loads the current revision detail', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        status: 'ready',
        view: 'current',
        menu_plan_id: 'mp-1',
        revision: 2,
        strategy_id: 'strategy-1',
        plan_status: 'superseded',
        has_replacements: true,
        plan: planPayload,
      },
    });

    const detail = await getMenuPlanDetail('mp-1');
    expect(api.get).toHaveBeenCalledWith('/api/menu/mp-1');
    expect(detail?.view).toBe('current');
    expect(detail?.revision).toBe(2);
    expect(detail?.has_replacements).toBe(true);
    expect(detail?.plan.menu_plan_id).toBe('mp-1');
    expect(detail?.plan.strategy_id).toBe('strategy-1');
  });

  it('loads the immutable original snapshot', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        status: 'ready',
        view: 'original',
        menu_plan_id: 'mp-1',
        revision: 1,
        strategy_id: 'strategy-1',
        plan_status: 'superseded',
        has_replacements: true,
        plan: planPayload,
      },
    });

    const detail = await getMenuPlanOriginal('mp-1');
    expect(api.get).toHaveBeenCalledWith('/api/menu/mp-1/original');
    expect(detail?.view).toBe('original');
    expect(detail?.revision).toBe(1);
  });

  it('returns null for non-ready or malformed responses', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { status: 'none' } });
    expect(await getMenuPlanDetail('mp-1')).toBeNull();

    vi.mocked(api.get).mockResolvedValue({
      data: { status: 'ready', plan: { summary: 'пусто' } },
    });
    expect(await getMenuPlanDetail('mp-1')).toBeNull();
  });

  it('escapes menu plan ids in paths', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { status: 'none' } });
    await getMenuPlanDetail('a/b');
    expect(api.get).toHaveBeenCalledWith('/api/menu/a%2Fb');
  });
});
