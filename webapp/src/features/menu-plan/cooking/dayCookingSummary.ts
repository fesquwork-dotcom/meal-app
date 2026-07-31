import { COOKING_LABELS } from '@/features/menu-plan/cooking/constants';
import { dayHasCookingMetadata } from '@/features/menu-plan/cooking/types';
import type { DayCookingOverviewStatus } from '@/features/menu-plan/cooking/types';
import type { DayMeal } from '@/types/menu';
import { pluralForm } from '@/utils/pluralize';

export interface DayCookingSummaryResult {
  text: string;
  cookCount: number;
  leftoverCount: number;
  noCookCount: number;
}

export function getDayCookingOverviewStatus(meals: DayMeal[]): DayCookingOverviewStatus {
  if (!dayHasCookingMetadata(meals)) {
    return 'unknown';
  }

  const cookCount = meals.filter((meal) => meal.requires_cooking === true).length;
  if (cookCount > 0) {
    return 'cook';
  }

  const leftoverCount = meals.filter((meal) => meal.uses_leftovers === true).length;
  if (leftoverCount > 0) {
    return 'leftovers';
  }

  return 'no_cook';
}

export function getDayCookingSummary(meals: DayMeal[]): DayCookingSummaryResult | null {
  if (!dayHasCookingMetadata(meals)) {
    return null;
  }

  const cookCount = meals.filter((meal) => meal.requires_cooking === true).length;
  const leftoverCount = meals.filter((meal) => meal.uses_leftovers === true).length;
  const noCookCount = meals.filter(
    (meal) => meal.requires_cooking === false && meal.uses_leftovers !== true,
  ).length;

  if (cookCount === 0 && leftoverCount === 0) {
    return {
      text: COOKING_LABELS.todayNoCooking,
      cookCount,
      leftoverCount,
      noCookCount,
    };
  }

  if (cookCount > 0 && leftoverCount === 0) {
    const dishWord = pluralForm(cookCount, ['блюдо', 'блюда', 'блюд']);
    return {
      text: `${COOKING_LABELS.todayCooking}: ${cookCount} ${dishWord}`,
      cookCount,
      leftoverCount,
      noCookCount,
    };
  }

  const parts: string[] = [];
  if (cookCount > 0) {
    parts.push(`${cookCount} ${pluralForm(cookCount, ['готовка', 'готовки', 'готовок'])}`);
  }
  if (leftoverCount > 0) {
    parts.push(
      `${leftoverCount} ${pluralForm(leftoverCount, ['блюдо', 'блюда', 'блюд'])} из заготовок`,
    );
  }

  return {
    text: `${COOKING_LABELS.todayCookingMixed}: ${parts.join(', ')}`,
    cookCount,
    leftoverCount,
    noCookCount,
  };
}
