import { api } from '@/api/client';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import type { GenerateMenuRequest } from '@/types/api';
import type { MenuPlanApiRecord } from '@/types/menu';

/**
 * Legacy sync generation (POST /api/generate-menu).
 * Production UI uses async generation jobs via `@/api/generationJobs`;
 * kept for tests / transitional helpers (e.g. fetchAndNormalizeMenu).
 */
export async function generateMenu(request: GenerateMenuRequest) {
  const { data } = await api.post<MenuPlanApiRecord>('/api/generate-menu', request);
  return normalizeMenuPlan(data);
}
