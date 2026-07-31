import type {
  MenuHistoryItem,
  MenuHistoryPage,
  MenuPlanHistoryStatus,
} from '@/types/menuHistory';

const MAX_PAGE_ITEMS = 20;
const MAX_SUMMARY_LENGTH = 300;

function objectValue(value: unknown): Record<string, unknown> | null {
  return value != null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function nonEmptyString(value: unknown, limit: number): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed && trimmed.length <= limit ? trimmed : null;
}

function nonNegativeNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
    ? value
    : null;
}

function positiveInt(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1
    ? value
    : null;
}

function normalizeItem(value: unknown): MenuHistoryItem | null {
  const item = objectValue(value);
  if (!item) return null;
  const menuPlanId = nonEmptyString(item.menu_plan_id, 80);
  const status = item.plan_status;
  const createdAt = nonEmptyString(item.created_at, 40);
  if (
    !menuPlanId ||
    !createdAt ||
    (status !== 'active' && status !== 'superseded')
  ) {
    return null;
  }
  return {
    menu_plan_id: menuPlanId,
    plan_status: status as MenuPlanHistoryStatus,
    created_at: createdAt,
    plan_start_date: nonEmptyString(item.plan_start_date, 20),
    days: positiveInt(item.days),
    total_cost: nonNegativeNumber(item.total_cost),
    summary: nonEmptyString(item.summary, MAX_SUMMARY_LENGTH),
    has_replacements: item.has_replacements === true,
  };
}

export function normalizeMenuHistoryPage(value: unknown): MenuHistoryPage {
  const page = objectValue(value);
  if (!page) {
    return { items: [], next_cursor: null };
  }
  const items = Array.isArray(page.items)
    ? page.items
        .map(normalizeItem)
        .filter((item): item is MenuHistoryItem => item !== null)
        .slice(0, MAX_PAGE_ITEMS)
    : [];
  return {
    items,
    next_cursor: nonEmptyString(page.next_cursor, 200),
  };
}
