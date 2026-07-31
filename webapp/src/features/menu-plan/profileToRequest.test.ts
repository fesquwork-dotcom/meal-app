import { describe, expect, it, vi } from 'vitest';
import {
  formatPlanStartDate,
  planStartDateToPreviewRequest,
} from '@/features/menu-plan/profileToRequest';

describe('planStartDateToPreviewRequest', () => {
  it('adds local date-only plan_start_date', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 6, 13, 23, 30));

    expect(formatPlanStartDate()).toBe('2026-07-13');
    expect(planStartDateToPreviewRequest('2026-07-13')).toEqual({
      plan_start_date: '2026-07-13',
    });
    expect(planStartDateToPreviewRequest()).toEqual({});

    vi.useRealTimers();
  });
});
