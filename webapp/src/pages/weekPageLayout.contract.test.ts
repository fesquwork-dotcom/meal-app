import { describe, expect, it } from 'vitest';

import weekPageSource from '@/pages/WeekPage.tsx?raw';

/** Sprint 10.3.4 / 10.3.5: Week page shows the menu first; header stays compact. */
describe('week page layout contract', () => {
  it('does not render the "План готовки" block', () => {
    expect(weekPageSource).not.toContain('CookingWeekOverview');
    expect(weekPageSource).not.toContain('План готовки');
  });

  it('uses a single compact WeekHeader instead of stacked info cards', () => {
    expect(weekPageSource).toContain('WeekHeader');
    expect(weekPageSource).not.toContain('WeekMealProgress');
    expect(weekPageSource).not.toContain('grid-cols-3');
    expect(weekPageSource).toContain('calculateMealProgress');
    expect(weekPageSource).toContain('onOpenSettings');
  });

  it('starts the day list right after WeekHeader', () => {
    const headerIndex = weekPageSource.indexOf('<WeekHeader');
    const daysIndex = weekPageSource.indexOf('<DayPlanCard');
    expect(headerIndex).toBeGreaterThan(-1);
    expect(daysIndex).toBeGreaterThan(headerIndex);
    const between = weekPageSource.slice(headerIndex, daysIndex);
    expect(between).not.toContain('StrategyExplanationBlock');
    expect(between).not.toContain('AppliedPlanSettingsBlock');
  });

  it('keeps secondary strategy context below the day list', () => {
    const daysIndex = weekPageSource.indexOf('<DayPlanCard');
    expect(weekPageSource.indexOf('<StrategyExplanationBlock')).toBeGreaterThan(daysIndex);
    expect(weekPageSource.indexOf('<AppliedPlanSettingsBlock')).toBeGreaterThan(daysIndex);
    expect(weekPageSource).toContain('budgetUtilizationText');
  });

  it('keeps Replace Meal, recipe open and basket navigation wired', () => {
    expect(weekPageSource).toContain('onRequestMealReplacement');
    expect(weekPageSource).toContain('openReplaceSheet');
    expect(weekPageSource).toContain('handleOpenRecipe');
    expect(weekPageSource).toContain('ROUTES.BASKET');
    expect(weekPageSource).toContain('usePositiveEvents');
  });
});
