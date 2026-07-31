function isStorageAvailable(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    const testKey = '__meal_planner_storage_test__';
    window.localStorage.setItem(testKey, '1');
    window.localStorage.removeItem(testKey);
    return true;
  } catch {
    return false;
  }
}

/** Safely reads and parses a value from localStorage. */
export function getStorageItem<T>(key: string): T | null {
  if (!isStorageAvailable()) {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) {
      return null;
    }

    return JSON.parse(raw) as T;
  } catch (error: unknown) {
    if (import.meta.env.DEV) {
      console.warn(`[storage] Failed to read key "${key}":`, error);
    }
    return null;
  }
}

/** Safely serializes and writes a value to localStorage. */
export function setStorageItem<T>(key: string, value: T): boolean {
  if (!isStorageAvailable()) {
    return false;
  }

  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error: unknown) {
    if (import.meta.env.DEV) {
      console.warn(`[storage] Failed to write key "${key}":`, error);
    }
    return false;
  }
}

/** Removes a value from localStorage. */
export function removeStorageItem(key: string): void {
  if (!isStorageAvailable()) {
    return;
  }

  try {
    window.localStorage.removeItem(key);
  } catch (error: unknown) {
    if (import.meta.env.DEV) {
      console.warn(`[storage] Failed to remove key "${key}":`, error);
    }
  }
}
