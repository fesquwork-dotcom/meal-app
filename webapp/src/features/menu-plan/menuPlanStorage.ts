import { STORAGE_KEYS } from '@/constants/storage';
import { removeStorageItem, setStorageItem } from '@/lib/storage';
import { readVersionedStorage, wrapForStorage } from '@/lib/storageVersion';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import type { MenuPlan } from '@/types/menu';

/** Restores a normalized menu plan from storage or removes invalid data. */
export function loadMenuPlanFromStorage(): MenuPlan | null {
  const stored = readVersionedStorage<unknown>(STORAGE_KEYS.MENU_PLAN);

  if (stored === null) {
    return null;
  }

  const plan = normalizeMenuPlan(stored);

  if (!plan) {
    removeStorageItem(STORAGE_KEYS.MENU_PLAN);
    return null;
  }

  return plan;
}

/** Persists a normalized menu plan to storage. */
export function persistMenuPlan(plan: MenuPlan): boolean {
  return setStorageItem(STORAGE_KEYS.MENU_PLAN, wrapForStorage(plan));
}

/** Removes persisted menu plan from storage. */
export function clearPersistedMenuPlan(): void {
  removeStorageItem(STORAGE_KEYS.MENU_PLAN);
}
