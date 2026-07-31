import { api } from '@/api/client';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import type { MenuPlan } from '@/types/menu';

interface CurrentMenuPlanResponse {
  status?: string;
  menu_plan_id?: string;
  revision?: number;
  strategy_id?: string;
  plan?: Record<string, unknown>;
}

/**
 * Sprint 7.2 — reads the authoritative current MenuPlan from the backend.
 * Returns null when the server has no durable plan for this user.
 */
export async function getCurrentMenuPlan(): Promise<MenuPlan | null> {
  const { data } = await api.get<CurrentMenuPlanResponse>('/api/menu/current');
  if (data?.status !== 'ready' || !data.plan) {
    return null;
  }
  return normalizeMenuPlan({
    ...data.plan,
    strategy_id: data.strategy_id,
    menu_plan_id: data.menu_plan_id,
    menu_plan_revision: data.revision,
  });
}
