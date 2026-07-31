import { useMemo } from 'react';
import { collectBasketItemIdsFromMenuPlan } from '@/features/basket/basketUtils';
import { useBasketState } from '@/features/basket/useBasketState';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';

export interface BasketProgress {
  totalCount: number;
  checkedCount: number;
  remainingCount: number;
  progressPercent: number;
  currentItemIds: string[];
}

export function useBasketProgress(): BasketProgress {
  const { menuPlan } = useMenuPlan();
  const { checkedItemIds } = useBasketState();

  const currentItemIds = useMemo(
    () => collectBasketItemIdsFromMenuPlan(menuPlan),
    [menuPlan],
  );

  return useMemo(() => {
    const totalCount = currentItemIds.length;
    const checkedCount = currentItemIds.filter((id) => checkedItemIds.has(id)).length;
    const remainingCount = Math.max(totalCount - checkedCount, 0);
    const progressPercent =
      totalCount > 0 ? Math.min(Math.round((checkedCount / totalCount) * 100), 100) : 0;

    return {
      totalCount,
      checkedCount,
      remainingCount,
      progressPercent,
      currentItemIds,
    };
  }, [currentItemIds, checkedItemIds]);
}
