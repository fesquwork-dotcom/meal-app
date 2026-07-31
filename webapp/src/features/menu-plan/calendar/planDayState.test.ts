import { describe, expect, it } from 'vitest';
import {
  calendarDayDiff,
  formatLocalDate,
  parseLocalDate,
} from '@/features/menu-plan/calendar/dateHelpers';
import {
  getHomePlanHeader,
  getPlanDayState,
  getPlanDayTitle,
} from '@/features/menu-plan/calendar/planDayState';

function localDate(value: string): Date {
  const parsed = parseLocalDate(value);
  if (!parsed) {
    throw new Error(`Invalid test date ${value}`);
  }
  return parsed;
}

describe('plan calendar helpers', () => {
  it('maps start date to day 1', () => {
    expect(
      getPlanDayState({
        planStartDate: '2026-07-13',
        planLength: 7,
        currentDate: localDate('2026-07-13'),
      }),
    ).toMatchObject({ kind: 'active', dayNumber: 1, dayIndex: 0 });
  });

  it('maps next calendar day to day 2', () => {
    expect(
      getPlanDayState({
        planStartDate: '2026-07-13',
        planLength: 7,
        currentDate: localDate('2026-07-14'),
      }),
    ).toMatchObject({ kind: 'active', dayNumber: 2, dayIndex: 1 });
  });

  it('keeps last day active', () => {
    expect(
      getPlanDayState({
        planStartDate: '2026-07-13',
        planLength: 7,
        currentDate: localDate('2026-07-19'),
      }),
    ).toMatchObject({ kind: 'active', dayNumber: 7, dayIndex: 6 });
  });

  it('returns completed after plan end', () => {
    expect(
      getPlanDayState({
        planStartDate: '2026-07-13',
        planLength: 7,
        currentDate: localDate('2026-07-20'),
      }),
    ).toMatchObject({ kind: 'completed', daysSinceCompletion: 1 });
  });

  it('returns before_start before plan begins', () => {
    expect(
      getPlanDayState({
        planStartDate: '2026-07-14',
        planLength: 7,
        currentDate: localDate('2026-07-13'),
      }),
    ).toMatchObject({ kind: 'before_start', daysUntilStart: 1 });
  });

  it('supports one-day plan', () => {
    expect(
      getPlanDayState({
        planStartDate: '2026-07-13',
        planLength: 1,
        currentDate: localDate('2026-07-13'),
      }),
    ).toMatchObject({ kind: 'active', dayNumber: 1 });
  });

  it('handles month and year boundaries', () => {
    expect(calendarDayDiff(localDate('2026-01-31'), localDate('2026-02-01'))).toBe(1);
    expect(calendarDayDiff(localDate('2026-12-31'), localDate('2027-01-01'))).toBe(1);
  });

  it('accepts leap day and rejects invalid dates', () => {
    expect(formatLocalDate(localDate('2024-02-29'))).toBe('2024-02-29');
    expect(parseLocalDate('2026-02-31')).toBeNull();
    expect(parseLocalDate('13.07.2026')).toBeNull();
  });

  it('does not shift across DST-like calendar dates', () => {
    expect(calendarDayDiff(localDate('2026-03-28'), localDate('2026-03-29'))).toBe(1);
  });

  it('returns legacy without start date and invalid for bad date', () => {
    expect(
      getPlanDayState({ planStartDate: undefined, planLength: 7, currentDate: localDate('2026-07-13') }),
    ).toEqual({ kind: 'legacy' });
    expect(
      getPlanDayState({ planStartDate: '2026-02-31', planLength: 7, currentDate: localDate('2026-07-13') }),
    ).toEqual({ kind: 'invalid' });
  });

  it('formats active header and day labels', () => {
    const state = getPlanDayState({
      planStartDate: '2026-07-13',
      planLength: 7,
      currentDate: localDate('2026-07-16'),
    });

    expect(getHomePlanHeader(state)).toMatchObject({ title: 'Сегодня · День 4' });
    expect(getPlanDayTitle('День 4', 3, '2026-07-13')).toContain('День 4 ·');
  });

  it('does not mutate input date', () => {
    const input = localDate('2026-07-13');
    const before = input.getTime();

    getPlanDayState({ planStartDate: '2026-07-13', planLength: 7, currentDate: input });

    expect(input.getTime()).toBe(before);
  });
});
