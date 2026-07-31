import { api } from '@/api/client';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import type { MenuPlan } from '@/types/menu';

export interface ReplaceMealRequest {
  strategy_id: string;
  menu_plan: MenuPlan;
  meal_id: string;
  reason?: string | null;
  reason_code?: string | null;
  target_ingredient?: string | null;
  replacement_request_id?: string | null;
  /** Sprint 7.2 — durable plan identity (omitted for legacy plans). */
  menu_plan_id?: string | null;
  expected_revision?: number | null;
}

export interface ReplaceMealResponse {
  menu_plan: MenuPlan;
  replaced_meal_id: string;
  changed_meal_ids: string[];
  menu_plan_id?: string | null;
  revision?: number | null;
}

export async function replaceMeal(request: ReplaceMealRequest): Promise<ReplaceMealResponse> {
  const { data } = await api.post<ReplaceMealResponse>('/api/menu/replace-meal', request);
  const normalized = normalizeMenuPlan(
    data.menu_plan_id && data.revision
      ? {
          ...data.menu_plan,
          menu_plan_id: data.menu_plan_id,
          menu_plan_revision: data.revision,
        }
      : data.menu_plan,
  );
  if (!normalized) {
    throw new Error('Invalid replacement response');
  }
  return {
    ...data,
    menu_plan: normalized,
  };
}
