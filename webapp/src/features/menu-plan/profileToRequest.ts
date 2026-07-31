import type { StrategyPreviewRequest } from '@/types/api';
import { formatLocalDate } from '@/features/menu-plan/calendar/dateHelpers';

export function formatPlanStartDate(date: Date = new Date()): string {
  return formatLocalDate(date);
}

export function planStartDateToPreviewRequest(planStartDate?: string): StrategyPreviewRequest {
  return planStartDate ? { plan_start_date: planStartDate } : {};
}
