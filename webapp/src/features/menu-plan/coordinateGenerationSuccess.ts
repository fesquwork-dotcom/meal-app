import { STORAGE_KEYS } from '@/constants/storage';
import { removeStorageItem } from '@/lib/storage';
import { persistMenuPlan } from '@/features/menu-plan/menuPlanStorage';
import type { MenuPlan } from '@/types/menu';
import type { Profile } from '@/types/profile';

export interface GenerationSuccessCallbacks {
  setMenuPlan: (plan: MenuPlan) => void;
  onProfileGenerationSuccess: (profile: Profile) => void;
}

/**
 * Single coordinator for post-generation side effects:
 * persist menu, clear basket checked storage, clear profile draft, sync profile.
 * Basket checked state is cleared by MenuPlanBasketSync when fingerprint changes.
 */
export function coordinateGenerationSuccess(
  plan: MenuPlan,
  profile: Profile,
  callbacks: GenerationSuccessCallbacks,
): void {
  callbacks.setMenuPlan(plan);
  persistMenuPlan(plan);
  removeStorageItem(STORAGE_KEYS.BASKET_CHECKED);
  removeStorageItem(STORAGE_KEYS.PROFILE_DRAFT);
  removeStorageItem(STORAGE_KEYS.POSITIVE_EVENT_MARKS);
  callbacks.onProfileGenerationSuccess(profile);
}
