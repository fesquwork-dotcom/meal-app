import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FC,
  type ReactNode,
} from 'react';
import { BasketContext, type BasketContextValue } from '@/features/basket/BasketContext';
import {
  clearPersistedBasketChecked,
  loadBasketCheckedFromStorage,
  persistBasketChecked,
} from '@/features/basket/basketStorage';

export interface BasketProviderProps {
  children: ReactNode;
}

export const BasketProvider: FC<BasketProviderProps> = ({ children }) => {
  const [checkedItemIds, setCheckedItemIds] = useState<Set<string>>(() => new Set());
  const [isBasketHydrated, setIsBasketHydrated] = useState(false);

  useEffect(() => {
    const storedIds = loadBasketCheckedFromStorage();
    if (storedIds.length > 0) {
      setCheckedItemIds(new Set(storedIds));
    }
    setIsBasketHydrated(true);
  }, []);

  useEffect(() => {
    if (!isBasketHydrated) {
      return;
    }

    persistBasketChecked(Array.from(checkedItemIds));
  }, [checkedItemIds, isBasketHydrated]);

  const toggleItem = useCallback((id: string) => {
    setCheckedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const markAll = useCallback((ids: string[]) => {
    setCheckedItemIds(new Set(ids));
  }, []);

  const clearAll = useCallback(() => {
    setCheckedItemIds(new Set());
    if (isBasketHydrated) {
      clearPersistedBasketChecked();
    }
  }, [isBasketHydrated]);

  const isChecked = useCallback(
    (id: string) => checkedItemIds.has(id),
    [checkedItemIds],
  );

  const value = useMemo<BasketContextValue>(
    () => ({
      checkedItemIds,
      checkedCount: checkedItemIds.size,
      isBasketHydrated,
      toggleItem,
      markAll,
      clearAll,
      isChecked,
    }),
    [checkedItemIds, isBasketHydrated, toggleItem, markAll, clearAll, isChecked],
  );

  return <BasketContext.Provider value={value}>{children}</BasketContext.Provider>;
};
