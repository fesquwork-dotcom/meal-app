/**
 * Russian plural forms: [one, few, many]
 * e.g. pluralize(5, ['день', 'дня', 'дней']) → '5 дней'
 */
export function pluralForm(count: number, forms: [string, string, string]): string {
  const abs = Math.abs(count) % 100;
  const last = abs % 10;

  if (last === 1 && abs !== 11) return forms[0];
  if (last >= 2 && last <= 4 && (abs < 10 || abs >= 20)) return forms[1];
  return forms[2];
}

export function pluralize(count: number, forms: [string, string, string]): string {
  return `${count} ${pluralForm(count, forms)}`;
}
