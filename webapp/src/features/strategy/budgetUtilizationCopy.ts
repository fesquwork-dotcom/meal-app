/** Build budget utilization copy for StrategyExplanation (Sprint 10.5.4). */

export function buildBudgetUtilizationText(input: {
  budgetLimit?: number | null;
  shoppingCost?: number | null;
  recipeCost?: number | null;
  budgetUsagePercent?: number | null;
}): string | null {
  const budget = input.budgetLimit;
  const shopping = input.shoppingCost;
  const usage = input.budgetUsagePercent;
  if (
    typeof budget !== 'number' ||
    budget <= 0 ||
    typeof shopping !== 'number' ||
    shopping < 0 ||
    typeof usage !== 'number' ||
    !Number.isFinite(usage)
  ) {
    return null;
  }

  const formatRub = (value: number) =>
    `${Math.round(value).toLocaleString('ru-RU')} ₽`;

  const usageLabel = Number.isInteger(usage) ? `${usage}` : usage.toFixed(1);
  let text =
    `Использовано ${usageLabel}% бюджета. ` +
    `Стоимость покупки ${formatRub(shopping)} из ${formatRub(budget)}.`;

  const recipe = input.recipeCost;
  if (typeof recipe === 'number' && shopping - recipe > 0.5) {
    text +=
      ' Стоимость покупки выше стоимости рецептов, так как часть продуктов приобретается полными упаковками.';
  }

  return text;
}
