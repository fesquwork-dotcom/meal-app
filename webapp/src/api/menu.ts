import { api } from '@/api/client';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import type { GenerateMenuRequest } from '@/types/api';
import type { MenuPlanApiRecord } from '@/types/menu';

export async function generateMenu(request: GenerateMenuRequest) {
  const { data } = await api.post<MenuPlanApiRecord>('/api/generate-menu', request);
  return normalizeMenuPlan(data);
}
