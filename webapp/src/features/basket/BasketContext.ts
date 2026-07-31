import { createContext } from 'react';

export interface BasketContextValue {
  checkedItemIds: Set<string>;
  checkedCount: number;
  isBasketHydrated: boolean;
  toggleItem: (id: string) => void;
  markAll: (ids: string[]) => void;
  clearAll: () => void;
  isChecked: (id: string) => boolean;
}

export const BasketContext = createContext<BasketContextValue | null>(null);
