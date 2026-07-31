import { beforeEach, describe, expect, it, vi } from 'vitest';

import { reconcileMenuPlan } from '@/features/menu-plan/menuPlanSync';
import type { MenuPlan } from '@/types/menu';

vi.mock('@/api/menuPlan', () => ({
  getCurrentMenuPlan: vi.fn(),
}));

import { getCurrentMenuPlan } from '@/api/menuPlan';

function buildPlan(overrides: Partial<MenuPlan> = {}): MenuPlan {
  return {
    summary: 'План',
    plan_start_date: '2026-07-13',
    strategy_id: 'strategy-1',
    total_cost: 1000,
    days_plan: [
      {
        day: 'День 1',
        breakfast: 'Овсянка',
        lunch: '',
        dinner: '',
        meals: [{ type: 'breakfast', recipe_name: 'Овсянка', uses_leftovers: false }],
      },
    ],
    recipes: [],
    basket: [],
    ...overrides,
  };
}

describe('reconcileMenuPlan', () => {
  beforeEach(() => {
    vi.mocked(getCurrentMenuPlan).mockReset();
  });

  it('never touches a legacy local plan without durable identity', async () => {
    const legacy = buildPlan();
    const result = await reconcileMenuPlan(legacy);
    expect(result).toBeNull();
    expect(getCurrentMenuPlan).not.toHaveBeenCalled();
  });

  it('restores the server plan when there is no local plan', async () => {
    const server = buildPlan({ menu_plan_id: 'mp-1', menu_plan_revision: 3 });
    vi.mocked(getCurrentMenuPlan).mockResolvedValue(server);

    const result = await reconcileMenuPlan(null);
    expect(result).toBe(server);
  });

  it('keeps local cache when server has no durable plan', async () => {
    vi.mocked(getCurrentMenuPlan).mockResolvedValue(null);
    const local = buildPlan({ menu_plan_id: 'mp-1', menu_plan_revision: 1 });
    expect(await reconcileMenuPlan(local)).toBeNull();
  });

  it('adopts a newer server revision of the same plan', async () => {
    const server = buildPlan({ menu_plan_id: 'mp-1', menu_plan_revision: 4 });
    vi.mocked(getCurrentMenuPlan).mockResolvedValue(server);
    const local = buildPlan({ menu_plan_id: 'mp-1', menu_plan_revision: 2 });
    expect(await reconcileMenuPlan(local)).toBe(server);
  });

  it('keeps local state when revisions match', async () => {
    const server = buildPlan({ menu_plan_id: 'mp-1', menu_plan_revision: 2 });
    vi.mocked(getCurrentMenuPlan).mockResolvedValue(server);
    const local = buildPlan({ menu_plan_id: 'mp-1', menu_plan_revision: 2 });
    expect(await reconcileMenuPlan(local)).toBeNull();
  });

  it('adopts a different durable server plan', async () => {
    const server = buildPlan({ menu_plan_id: 'mp-2', menu_plan_revision: 1 });
    vi.mocked(getCurrentMenuPlan).mockResolvedValue(server);
    const local = buildPlan({ menu_plan_id: 'mp-1', menu_plan_revision: 5 });
    expect(await reconcileMenuPlan(local)).toBe(server);
  });

  it('keeps local cache when the fetch fails (offline)', async () => {
    vi.mocked(getCurrentMenuPlan).mockRejectedValue(new Error('network'));
    const local = buildPlan({ menu_plan_id: 'mp-1', menu_plan_revision: 1 });
    expect(await reconcileMenuPlan(local)).toBeNull();
  });
});
