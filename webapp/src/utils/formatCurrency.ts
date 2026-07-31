const currencyFormatter = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  maximumFractionDigits: 0,
});

export function formatCurrency(value: number): string {
  const safe = Number.isFinite(value) ? Math.max(0, value) : 0;
  return currencyFormatter.format(safe);
}
