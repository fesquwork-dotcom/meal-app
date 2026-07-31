import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getStorageItem,
  removeStorageItem,
  setStorageItem,
} from '@/lib/storage';

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

describe('storage', () => {
  it('writes and reads JSON values', () => {
    const payload = { hello: 'world', count: 2 };
    expect(setStorageItem('test-key', payload)).toBe(true);
    expect(getStorageItem<typeof payload>('test-key')).toEqual(payload);
  });

  it('returns null for broken JSON', () => {
    memoryStore.set('broken', '{not-json');
    expect(getStorageItem('broken')).toBeNull();
  });

  it('removes values', () => {
    setStorageItem('remove-me', { ok: true });
    removeStorageItem('remove-me');
    expect(getStorageItem('remove-me')).toBeNull();
  });

  it('does not throw when localStorage.setItem fails', () => {
    vi.stubGlobal('window', {
      localStorage: {
        getItem: () => null,
        setItem: () => {
          throw new Error('quota exceeded');
        },
        removeItem: () => undefined,
      },
    });

    expect(setStorageItem('fail-key', { value: 1 })).toBe(false);
  });
});
