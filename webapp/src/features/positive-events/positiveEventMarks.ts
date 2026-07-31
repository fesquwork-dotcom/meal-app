import { STORAGE_KEYS } from '@/constants/storage';
import { removeStorageItem, setStorageItem } from '@/lib/storage';
import { readVersionedStorage, wrapForStorage } from '@/lib/storageVersion';
import type { PositiveEventType } from '@/api/positiveEvents';

const MAX_MARKS = 200;
const MARK_PATTERN = /^(meal_cooked|meal_suited):[\w:.-]{1,100}$|^(shopping_completed|plan_completed)$/;

interface StoredMarks {
  strategyId: string;
  marks: string[];
}

/** Local key of one sent mark. Contains only technical ids, never dish names. */
export function buildMarkKey(eventType: PositiveEventType, mealId?: string | null): string {
  if (eventType === 'meal_cooked' || eventType === 'meal_suited') {
    return `${eventType}:${mealId ?? ''}`;
  }
  return eventType;
}

function parseStoredMarks(raw: unknown): StoredMarks | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }
  const record = raw as Record<string, unknown>;
  if (typeof record.strategyId !== 'string' || !record.strategyId) {
    return null;
  }
  if (!Array.isArray(record.marks)) {
    return null;
  }
  const marks = record.marks
    .filter((mark): mark is string => typeof mark === 'string' && MARK_PATTERN.test(mark))
    .slice(0, MAX_MARKS);
  return { strategyId: record.strategyId, marks };
}

/** Restores sent marks for one strategy; marks from other strategies are dropped. */
export function loadPositiveEventMarks(strategyId: string): Set<string> {
  const stored = parseStoredMarks(
    readVersionedStorage<unknown>(STORAGE_KEYS.POSITIVE_EVENT_MARKS),
  );
  if (!stored || stored.strategyId !== strategyId) {
    return new Set();
  }
  return new Set(stored.marks);
}

/** Persists sent marks for the current strategy only. */
export function persistPositiveEventMarks(strategyId: string, marks: Set<string>): boolean {
  const payload: StoredMarks = {
    strategyId,
    marks: [...marks].slice(0, MAX_MARKS),
  };
  return setStorageItem(STORAGE_KEYS.POSITIVE_EVENT_MARKS, wrapForStorage(payload));
}

/** Removes persisted marks entirely. */
export function clearPositiveEventMarks(): void {
  removeStorageItem(STORAGE_KEYS.POSITIVE_EVENT_MARKS);
}
