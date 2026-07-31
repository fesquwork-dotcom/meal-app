import {
  addCalendarDays,
  calendarDayDiff,
  formatFullPlanDate,
  formatPlanDayDate,
  parseLocalDate,
} from '@/features/menu-plan/calendar/dateHelpers';

export type PlanDayState =
  | { kind: 'before_start'; daysUntilStart: number; startDate: Date }
  | { kind: 'active'; dayNumber: number; dayIndex: number; date: Date }
  | { kind: 'completed'; daysSinceCompletion: number; endDate: Date }
  | { kind: 'legacy' }
  | { kind: 'invalid' };

export interface GetPlanDayStateInput {
  planStartDate: string | null | undefined;
  planLength: number;
  currentDate: Date;
}

export function getPlanDayState({
  planStartDate,
  planLength,
  currentDate,
}: GetPlanDayStateInput): PlanDayState {
  if (planStartDate === null || planStartDate === undefined) {
    return { kind: 'legacy' };
  }

  const startDate = parseLocalDate(planStartDate);
  if (!startDate || planLength < 1) {
    return { kind: 'invalid' };
  }

  const diff = calendarDayDiff(startDate, currentDate);
  if (diff < 0) {
    return {
      kind: 'before_start',
      daysUntilStart: Math.abs(diff),
      startDate,
    };
  }

  if (diff >= planLength) {
    return {
      kind: 'completed',
      daysSinceCompletion: diff - planLength + 1,
      endDate: addCalendarDays(startDate, planLength - 1),
    };
  }

  return {
    kind: 'active',
    dayNumber: diff + 1,
    dayIndex: diff,
    date: addCalendarDays(startDate, diff),
  };
}

export function getDateForPlanDay(planStartDate: string | null | undefined, dayIndex: number): Date | null {
  const startDate = parseLocalDate(planStartDate);
  if (!startDate || dayIndex < 0) {
    return null;
  }

  return addCalendarDays(startDate, dayIndex);
}

export function getPlanDayTitle(dayLabel: string, dayIndex: number, planStartDate: string | null | undefined): string {
  const date = getDateForPlanDay(planStartDate, dayIndex);
  if (!date) {
    return dayLabel;
  }

  return `${dayLabel} · ${formatPlanDayDate(date)}`;
}

export function getHomePlanHeader(state: PlanDayState): { title: string; subtitle?: string } {
  if (state.kind === 'active') {
    return {
      title: `Сегодня · День ${state.dayNumber}`,
      subtitle: formatFullPlanDate(state.date),
    };
  }

  if (state.kind === 'before_start') {
    return {
      title: state.daysUntilStart === 1 ? 'План начнётся завтра' : `План начнётся через ${state.daysUntilStart} дн.`,
      subtitle: `Первый день — ${formatFullPlanDate(state.startDate)}`,
    };
  }

  if (state.kind === 'completed') {
    return {
      title: 'План завершён',
      subtitle: 'Создайте новое меню, чтобы продолжить',
    };
  }

  if (state.kind === 'invalid') {
    return {
      title: 'Дата плана повреждена',
      subtitle: 'Первый день плана доступен ниже',
    };
  }

  return { title: 'Первый день плана' };
}
