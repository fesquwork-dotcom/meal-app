/**
 * Sprint 9.5 — localStorage keys cleared after a server-side user reset.
 */

import { STORAGE_KEYS } from '@/constants/storage';

const CLIENT_KEYS = [
  STORAGE_KEYS.MENU_PLAN,
  STORAGE_KEYS.BASKET_CHECKED,
  STORAGE_KEYS.PROFILE_DRAFT,
  STORAGE_KEYS.POSITIVE_EVENT_MARKS,
] as const;

export function clearClientStateAfterDevReset(): void {
  for (const key of CLIENT_KEYS) {
    try {
      localStorage.removeItem(key);
    } catch {
      // Ignore quota / private-mode failures.
    }
  }
}
