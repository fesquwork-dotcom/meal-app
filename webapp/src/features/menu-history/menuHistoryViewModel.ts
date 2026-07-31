import type { MenuHistoryItem, MenuPlanHistoryStatus, MenuPlanView } from '@/types/menuHistory';

const STATUS_LABELS: Record<MenuPlanHistoryStatus, string> = {
  active: 'Текущий план',
  superseded: 'Прошлый план',
};

export const VIEW_LABELS: Record<MenuPlanView, string> = {
  current: 'Текущий вариант',
  original: 'Исходный вариант',
};

const MONTHS_GENITIVE = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
];

export function formatHistoryDate(isoDate: string | null): string | null {
  if (!isoDate) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
  if (!match) return null;
  const month = Number.parseInt(match[2], 10);
  const day = Number.parseInt(match[3], 10);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return `${day} ${MONTHS_GENITIVE[month - 1]} ${match[1]}`;
}

export interface MenuHistoryItemViewModel {
  menuPlanId: string;
  title: string;
  statusLabel: string;
  isActive: boolean;
  detailsLine: string | null;
  summary: string | null;
  replacementsNote: string | null;
}

function daysLabel(days: number): string {
  const remainder10 = days % 10;
  const remainder100 = days % 100;
  if (remainder10 === 1 && remainder100 !== 11) return `${days} день`;
  if (remainder10 >= 2 && remainder10 <= 4 && (remainder100 < 12 || remainder100 > 14)) {
    return `${days} дня`;
  }
  return `${days} дней`;
}

export function buildHistoryItemViewModel(item: MenuHistoryItem): MenuHistoryItemViewModel {
  const startDate = formatHistoryDate(item.plan_start_date);
  const details: string[] = [];
  if (item.days !== null) details.push(daysLabel(item.days));
  if (item.total_cost !== null) details.push(`${Math.round(item.total_cost)} ₽`);
  return {
    menuPlanId: item.menu_plan_id,
    title: startDate ? `План с ${startDate}` : 'План недели',
    statusLabel: STATUS_LABELS[item.plan_status],
    isActive: item.plan_status === 'active',
    detailsLine: details.length > 0 ? details.join(' · ') : null,
    summary: item.summary,
    replacementsNote: item.has_replacements ? 'Были замены блюд' : null,
  };
}
