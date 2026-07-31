import { STORAGE_KEYS } from '@/constants/storage';
import { removeStorageItem, setStorageItem } from '@/lib/storage';
import { readVersionedStorage, wrapForStorage } from '@/lib/storageVersion';

function parseCheckedIds(raw: unknown): string[] {
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw.filter((id): id is string => typeof id === 'string');
}

/** Restores checked basket item ids from storage. */
export function loadBasketCheckedFromStorage(): string[] {
  const stored = readVersionedStorage<unknown>(STORAGE_KEYS.BASKET_CHECKED);
  return parseCheckedIds(stored);
}

/** Persists checked basket item ids to storage. */
export function persistBasketChecked(ids: string[]): boolean {
  return setStorageItem(STORAGE_KEYS.BASKET_CHECKED, wrapForStorage(ids));
}

/** Removes persisted basket checked state. */
export function clearPersistedBasketChecked(): void {
  removeStorageItem(STORAGE_KEYS.BASKET_CHECKED);
}
