/** Versioned client-side storage keys. */
export const STORAGE_KEYS = {
  MENU_PLAN: 'meal-planner:v1:menu-plan',
  BASKET_CHECKED: 'meal-planner:v1:basket-checked',
  PROFILE_DRAFT: 'meal-planner:v1:profile-draft',
  POSITIVE_EVENT_MARKS: 'meal-planner:v1:positive-event-marks',
} as const;

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];
