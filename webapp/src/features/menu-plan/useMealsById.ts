import { useMemo } from 'react';
import type { MenuPlan } from '@/types/menu';
import { buildMealsByIdIndex } from '@/features/menu-plan/cooking/mealsById';
import type { MealsByIdIndex } from '@/features/menu-plan/cooking/types';

export function useMealsById(menuPlan: MenuPlan | null): MealsByIdIndex {
  return useMemo(() => {
    if (!menuPlan) {
      return {};
    }
    return buildMealsByIdIndex(menuPlan);
  }, [menuPlan]);
}
