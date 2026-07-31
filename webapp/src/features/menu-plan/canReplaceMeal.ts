import type { MenuPlan } from '@/types/menu';
import { getPlanDayState, type PlanDayState } from '@/features/menu-plan/calendar/planDayState';

export interface ReplaceMealAvailability {
  canReplace: boolean;
  /** Per-condition facts for diagnostics; no guessing needed when it breaks. */
  reasons: {
    hasPlan: boolean;
    hasStrategyId: boolean;
    planStartDate: string | null | undefined;
    planLength: number;
    planDayStateKind: PlanDayState['kind'] | null;
  };
}

/** Full condition trace for the Replace button (used by dev diagnostics and tests). */
export function explainReplaceMealAvailability(
  menuPlan: MenuPlan | null,
  now = new Date(),
): ReplaceMealAvailability {
  if (!menuPlan?.strategy_id) {
    return {
      canReplace: false,
      reasons: {
        hasPlan: Boolean(menuPlan),
        hasStrategyId: false,
        planStartDate: menuPlan?.plan_start_date,
        planLength: menuPlan?.days_plan.length ?? 0,
        planDayStateKind: null,
      },
    };
  }

  const state = getPlanDayState({
    planStartDate: menuPlan.plan_start_date,
    planLength: menuPlan.days_plan.length,
    currentDate: now,
  });

  return {
    canReplace: state.kind === 'active' || state.kind === 'before_start',
    reasons: {
      hasPlan: true,
      hasStrategyId: true,
      planStartDate: menuPlan.plan_start_date,
      planLength: menuPlan.days_plan.length,
      planDayStateKind: state.kind,
    },
  };
}

/** Whether a meal can be replaced within the active strategy-backed plan. */
export function canReplaceMeal(menuPlan: MenuPlan | null, now = new Date()): boolean {
  return explainReplaceMealAvailability(menuPlan, now).canReplace;
}
