import { api } from '@/api/client';
import { normalizeMenuHistoryPage } from '@/features/menu-history/normalizeMenuHistory';
import { normalizePlanDelta } from '@/features/menu-history/normalizePlanDelta';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import type { MenuHistoryPage, MenuPlanDetail } from '@/types/menuHistory';
import type { PlanDeltaResult } from '@/types/planDelta';

interface MenuPlanDetailResponse {
  status?: string;
  view?: string;
  menu_plan_id?: string;
  revision?: number;
  strategy_id?: string;
  plan_status?: string;
  has_replacements?: boolean;
  plan?: Record<string, unknown>;
}

export async function getMenuHistory(cursor?: string | null): Promise<MenuHistoryPage> {
  const { data } = await api.get<unknown>('/api/menu/history', {
    params: cursor ? { cursor } : undefined,
  });
  return normalizeMenuHistoryPage(data);
}

function toDetail(data: MenuPlanDetailResponse): MenuPlanDetail | null {
  if (data?.status !== 'ready' || !data.plan) {
    return null;
  }
  const plan = normalizeMenuPlan({
    ...data.plan,
    strategy_id: data.strategy_id,
    menu_plan_id: data.menu_plan_id,
    menu_plan_revision: data.revision,
  });
  if (!plan) {
    return null;
  }
  return {
    plan,
    view: data.view === 'original' ? 'original' : 'current',
    revision: typeof data.revision === 'number' ? data.revision : 1,
    plan_status: data.plan_status === 'active' ? 'active' : 'superseded',
    has_replacements: data.has_replacements === true,
  };
}

/** Read-only detail: the latest validated revision of a durable plan. */
export async function getMenuPlanDetail(menuPlanId: string): Promise<MenuPlanDetail | null> {
  const { data } = await api.get<MenuPlanDetailResponse>(
    `/api/menu/${encodeURIComponent(menuPlanId)}`,
  );
  return toDetail(data);
}

/** Read-only detail: the immutable original snapshot (revision 1). */
export async function getMenuPlanOriginal(menuPlanId: string): Promise<MenuPlanDetail | null> {
  const { data } = await api.get<MenuPlanDetailResponse>(
    `/api/menu/${encodeURIComponent(menuPlanId)}/original`,
  );
  return toDetail(data);
}

interface PlanDeltaResponse {
  status?: string;
  menu_plan_id?: string;
  revision?: number;
  has_replacements?: boolean;
  delta?: unknown;
}

/** Sprint 7.4 — factual original→current differences of one durable plan. */
export async function getMenuPlanDelta(menuPlanId: string): Promise<PlanDeltaResult | null> {
  const { data } = await api.get<PlanDeltaResponse>(
    `/api/menu/${encodeURIComponent(menuPlanId)}/delta`,
  );
  if (data?.status !== 'ready' || typeof data.menu_plan_id !== 'string') {
    return null;
  }
  const delta = normalizePlanDelta(data.delta);
  if (!delta) {
    return null;
  }
  return {
    menu_plan_id: data.menu_plan_id,
    revision: typeof data.revision === 'number' ? data.revision : 1,
    has_replacements: data.has_replacements === true,
    delta,
  };
}
