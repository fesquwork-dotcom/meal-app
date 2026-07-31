import { describe, expect, it } from 'vitest';
import { buildBudgetUtilizationText } from '@/features/strategy/budgetUtilizationCopy';

describe('buildBudgetUtilizationText', () => {
  it('returns null when shopping cost or budget is missing', () => {
    expect(
      buildBudgetUtilizationText({
        budgetLimit: 6000,
        shoppingCost: null,
        budgetUsagePercent: 98,
      }),
    ).toBeNull();
  });

  it('describes usage percent and package gap', () => {
    const text = buildBudgetUtilizationText({
      budgetLimit: 6000,
      shoppingCost: 5870,
      recipeCost: 5120,
      budgetUsagePercent: 97.8,
    });
    expect(text).toContain('Использовано 97.8% бюджета');
    expect(text).toContain('упаковками');
  });

  it('omits package sentence when costs match', () => {
    const text = buildBudgetUtilizationText({
      budgetLimit: 6000,
      shoppingCost: 5400,
      recipeCost: 5400,
      budgetUsagePercent: 90,
    });
    expect(text).toContain('Использовано 90% бюджета');
    expect(text).not.toContain('упаковками');
  });
});
