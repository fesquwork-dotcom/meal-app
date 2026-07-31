import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  buildMarkKey,
  clearPositiveEventMarks,
  loadPositiveEventMarks,
  persistPositiveEventMarks,
} from '@/features/positive-events/positiveEventMarks';
import { STORAGE_KEYS } from '@/constants/storage';

const memoryStore = new Map<string, string>();

beforeEach(() => {
  memoryStore.clear();

  vi.stubGlobal('window', {
    localStorage: {
      getItem: (key: string) => memoryStore.get(key) ?? null,
      setItem: (key: string, value: string) => {
        memoryStore.set(key, value);
      },
      removeItem: (key: string) => {
        memoryStore.delete(key);
      },
    },
  });
});

describe('buildMarkKey', () => {
  it('scopes meal events by meal id and strategy events by type only', () => {
    expect(buildMarkKey('meal_cooked', 'd1-breakfast')).toBe('meal_cooked:d1-breakfast');
    expect(buildMarkKey('meal_suited', 'd2-lunch')).toBe('meal_suited:d2-lunch');
    expect(buildMarkKey('shopping_completed')).toBe('shopping_completed');
    expect(buildMarkKey('plan_completed', 'ignored')).toBe('plan_completed');
  });
});

describe('positive event marks storage', () => {
  it('persists and restores marks for the same strategy', () => {
    const marks = new Set([
      buildMarkKey('meal_cooked', 'd1-breakfast'),
      buildMarkKey('shopping_completed'),
    ]);
    expect(persistPositiveEventMarks('strategy-1', marks)).toBe(true);
    expect(loadPositiveEventMarks('strategy-1')).toEqual(marks);
  });

  it('drops marks that belong to another strategy', () => {
    persistPositiveEventMarks('strategy-1', new Set([buildMarkKey('plan_completed')]));
    expect(loadPositiveEventMarks('strategy-2').size).toBe(0);
  });

  it('filters malformed entries and unknown shapes', () => {
    memoryStore.set(
      STORAGE_KEYS.POSITIVE_EVENT_MARKS,
      JSON.stringify({
        version: 1,
        data: {
          strategyId: 'strategy-1',
          marks: [
            'meal_cooked:d1-breakfast',
            'unknown_event:x',
            42,
            'meal_replaced:d1-breakfast',
            'plan_completed',
          ],
        },
      }),
    );
    const restored = loadPositiveEventMarks('strategy-1');
    expect(restored).toEqual(new Set(['meal_cooked:d1-breakfast', 'plan_completed']));
  });

  it('returns empty set for corrupted payloads', () => {
    memoryStore.set(STORAGE_KEYS.POSITIVE_EVENT_MARKS, JSON.stringify({ version: 1, data: [] }));
    expect(loadPositiveEventMarks('strategy-1').size).toBe(0);
  });

  it('clears persisted marks', () => {
    persistPositiveEventMarks('strategy-1', new Set([buildMarkKey('plan_completed')]));
    clearPositiveEventMarks();
    expect(loadPositiveEventMarks('strategy-1').size).toBe(0);
  });
});
