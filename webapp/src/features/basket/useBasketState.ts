import { useContext } from 'react';
import { BasketContext } from '@/features/basket/BasketContext';
import type { BasketContextValue } from '@/features/basket/BasketContext';

export function useBasketState(): BasketContextValue {
  const context = useContext(BasketContext);

  if (!context) {
    throw new Error('useBasketState must be used within BasketProvider');
  }

  return context;
}
