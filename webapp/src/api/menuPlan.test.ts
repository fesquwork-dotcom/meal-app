import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getCurrentMenuPlan } from '@/api/menuPlan';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from '@/api/client';

const readyResponse = {
  status: 'ready',
  menu_plan_id: 'mp-1',
  revision: 2,
  strategy_id: 'strategy-1',
  plan_status: 'active',
  plan: {
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
  },
};

describe('getCurrentMenuPlan', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
  });

  it('returns null for status none', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { status: 'none' } });
    expect(await getCurrentMenuPlan()).toBeNull();
    expect(api.get).toHaveBeenCalledWith('/api/menu/current');
  });

  it('normalizes a ready plan with durable identity', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: readyResponse });
    const plan = await getCurrentMenuPlan();
    expect(plan?.menu_plan_id).toBe('mp-1');
    expect(plan?.menu_plan_revision).toBe(2);
    expect(plan?.strategy_id).toBe('strategy-1');
    expect(plan?.days_plan).toHaveLength(1);
  });

  it('returns null for a ready status without plan payload', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { status: 'ready', menu_plan_id: 'mp-1', revision: 1 },
    });
    expect(await getCurrentMenuPlan()).toBeNull();
  });

  it('returns null for malformed plan payload', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { ...readyResponse, plan: { summary: 'пусто' } },
    });
    expect(await getCurrentMenuPlan()).toBeNull();
  });
});
