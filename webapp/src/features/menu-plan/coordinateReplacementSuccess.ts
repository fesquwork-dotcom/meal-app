import { persistMenuPlan } from '@/features/menu-plan/menuPlanStorage';
import type { MenuPlan } from '@/types/menu';

export interface ReplacementSuccessCallbacks {
  setMenuPlan: (plan: MenuPlan) => void;
}

/** Persists updated menu plan after successful meal replacement. */
export function coordinateReplacementSuccess(
  plan: MenuPlan,
  callbacks: ReplacementSuccessCallbacks,
): void {
  callbacks.setMenuPlan(plan);
  persistMenuPlan(plan);
}
