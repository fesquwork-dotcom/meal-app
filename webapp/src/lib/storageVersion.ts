import { getStorageItem, removeStorageItem } from '@/lib/storage';

/** Current client storage schema version. */
export const CURRENT_STORAGE_VERSION = 1;

export interface VersionedPayload<T> {
  version: number;
  data: T;
}

// Future migrations will live here, e.g. migrateV1ToV2(payload).

/** Wraps data with the current storage version envelope. */
export function wrapForStorage<T>(data: T): VersionedPayload<T> {
  return { version: CURRENT_STORAGE_VERSION, data };
}

/** Unwraps versioned storage data. Returns null when version is incompatible. */
export function unwrapFromStorage<T>(raw: unknown): T | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }

  const envelope = raw as Partial<VersionedPayload<T>>;

  if (envelope.version !== CURRENT_STORAGE_VERSION || envelope.data === undefined) {
    return null;
  }

  return envelope.data;
}

/** Reads a versioned value and removes the key when the payload is invalid. */
export function readVersionedStorage<T>(key: string): T | null {
  const raw = getStorageItem<unknown>(key);

  if (raw === null) {
    return null;
  }

  const data = unwrapFromStorage<T>(raw);

  if (data === null) {
    removeStorageItem(key);
  }

  return data;
}
