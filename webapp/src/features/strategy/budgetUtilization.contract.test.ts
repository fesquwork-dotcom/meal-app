import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const weekHeader = readFileSync(
  resolve(__dirname, '../menu-plan/components/WeekHeader.tsx'),
  'utf-8',
);
const basket = readFileSync(resolve(__dirname, '../basket/Basket.tsx'), 'utf-8');
const weekPage = readFileSync(resolve(__dirname, '../../pages/WeekPage.tsx'), 'utf-8');

describe('Budget utilization UX contract (Sprint 10.5.4)', () => {
  it('shows budget usage in WeekHeader when shopping cost is known', () => {
    expect(weekHeader).toContain('week-budget-usage');
    expect(weekHeader).toContain('Использовано бюджета');
    expect(weekHeader).toContain('budgetUsagePercent');
  });

  it('shows dual cost block in Basket only when shopping exceeds recipe', () => {
    expect(basket).toContain('basket-dual-cost');
    expect(basket).toContain('Стоимость рецептов');
    expect(basket).toContain('Стоимость покупки');
    expect(basket).toContain('Причина: покупка полных упаковок');
  });

  it('wires utilization into week explanation', () => {
    expect(weekPage).toContain('buildBudgetUtilizationText');
    expect(weekPage).toContain('budgetUtilizationText');
  });
});
