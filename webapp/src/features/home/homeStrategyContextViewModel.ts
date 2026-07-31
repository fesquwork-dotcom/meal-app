import { calendarDayDiff, parseLocalDate } from '@/features/menu-plan/calendar/dateHelpers';
import type { CurrentStrategyResponse } from '@/types/strategy';

/**
 * Sprint 5.36 — Home strategy context block.
 *
 * Boundary: MenuPlan = блюда, рецепты и календарный день; Strategy = правила,
 * контекст и объяснение плана. This view model is metadata-only: `status:none`,
 * 404 or a read error simply hide the block and never affect the local MenuPlan.
 */

export type HomeStrategyLifecycleLabel = 'active' | 'before_start' | 'completed';

export interface HomeStrategyContextViewModel {
  visible: boolean;
  status: HomeStrategyLifecycleLabel | null;
  statusLabel: string | null;
  periodLabel: string | null;
  headline: string | null;
  /** Up to three applied settings lines. */
  settingsLines: string[];
}

const HIDDEN: HomeStrategyContextViewModel = {
  visible: false,
  status: null,
  statusLabel: null,
  periodLabel: null,
  headline: null,
  settingsLines: [],
};

const STATUS_LABELS: Record<HomeStrategyLifecycleLabel, string> = {
  active: 'План активен',
  before_start: 'План скоро начнётся',
  completed: 'План завершён',
};

const MAX_SETTINGS_LINES = 3;

function formatPeriodDate(date: Date): string {
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' }).format(date);
}

function resolveLifecycle(
  data: CurrentStrategyResponse,
  now: Date,
): HomeStrategyLifecycleLabel | null {
  if (data.status === 'completed' || data.status === 'superseded') {
    return 'completed';
  }
  if (data.status !== 'active') {
    return null;
  }

  const start = parseLocalDate(data.plan_start_date);
  const end = parseLocalDate(data.plan_end_date);
  if (start && calendarDayDiff(now, start) > 0) {
    return 'before_start';
  }
  if (end && calendarDayDiff(end, now) > 0) {
    return 'completed';
  }
  return 'active';
}

function buildPeriodLabel(data: CurrentStrategyResponse): string | null {
  const start = parseLocalDate(data.plan_start_date);
  const end = parseLocalDate(data.plan_end_date);
  if (!start || !end) {
    return null;
  }
  return `${formatPeriodDate(start)} — ${formatPeriodDate(end)}`;
}

function buildSettingsLines(data: CurrentStrategyResponse): string[] {
  const lines: string[] = [];
  const applied = data.applied_settings;
  if (!applied) {
    return lines;
  }

  if (applied.cooking) {
    lines.push(`Готовка до ${applied.cooking.cooking_time_limit} минут`);
    if (applied.cooking.prefer_faster_meals) {
      lines.push('Приоритет более быстрых блюд');
    }
  }
  if (applied.planning?.prefer_familiar_meals) {
    lines.push('Знакомые блюда в приоритете');
  }
  if (applied.behavior && applied.behavior.applied_count > 0) {
    lines.push(`Учтены наблюдения: ${applied.behavior.applied_count}`);
  }

  return lines.slice(0, MAX_SETTINGS_LINES);
}

/**
 * Builds the optional strategy metadata block for HomePage.
 * Hidden for `status: none`, missing data (404 / read error keeps resource
 * data null) — hiding this block is the only allowed consequence.
 */
export function buildHomeStrategyContextViewModel(
  data: CurrentStrategyResponse | null | undefined,
  now: Date,
): HomeStrategyContextViewModel {
  if (!data || data.status === 'none') {
    return HIDDEN;
  }

  const lifecycle = resolveLifecycle(data, now);
  if (!lifecycle) {
    return HIDDEN;
  }

  const periodLabel = buildPeriodLabel(data);
  const headline = data.explanation?.headline?.trim() || null;
  const settingsLines = buildSettingsLines(data);

  if (!periodLabel && !headline && settingsLines.length === 0) {
    return HIDDEN;
  }

  return {
    visible: true,
    status: lifecycle,
    statusLabel: STATUS_LABELS[lifecycle],
    periodLabel,
    headline,
    settingsLines,
  };
}
