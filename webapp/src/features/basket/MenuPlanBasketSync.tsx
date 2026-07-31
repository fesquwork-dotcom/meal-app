import { useEffect, useRef, type FC, type ReactNode } from 'react';
import { useBasketState } from '@/features/basket/useBasketState';
import { getMenuPlanFingerprint } from '@/features/menu-plan/menuPlanFingerprint';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';

/**
 * Clears basket checked state when a new menu plan replaces the previous one.
 */
export const MenuPlanBasketSync: FC<{ children: ReactNode }> = ({ children }) => {
  const { menuPlan } = useMenuPlan();
  const { clearAll } = useBasketState();
  const previousFingerprintRef = useRef<string | null>(null);

  useEffect(() => {
    if (!menuPlan) {
      previousFingerprintRef.current = null;
      return;
    }

    const fingerprint = getMenuPlanFingerprint(menuPlan);

    if (
      previousFingerprintRef.current !== null &&
      previousFingerprintRef.current !== fingerprint
    ) {
      clearAll();
    }

    previousFingerprintRef.current = fingerprint;
  }, [menuPlan, clearAll]);

  return children;
};
