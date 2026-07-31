import type { MealType } from '@/types/meal';
import { MEAL_TYPE_LABELS } from '@/types/meal';
import type { ProfileCooktime, ProfileGoal, ProfileProtein } from '@/types/profile';

export interface SelectOption<T extends string = string> {
  value: T;
  label: string;
  description?: string;
}

export const GOAL_OPTIONS: SelectOption<ProfileGoal>[] = [
  { value: 'healthy', label: 'Правильное питание', description: '🥗' },
  { value: 'home', label: 'Домашняя еда', description: '🏠' },
  { value: 'muscle', label: 'Набор массы', description: '💪' },
  { value: 'weightloss', label: 'Похудение', description: '⚖️' },
  { value: 'restaurant', label: 'Ресторан дома', description: '🍽' },
  { value: 'budget', label: 'Экономно', description: '💰' },
];

export const PROTEIN_OPTIONS: SelectOption<ProfileProtein>[] = [
  { value: 'any', label: 'Любые' },
  { value: 'chicken', label: 'Курица' },
  { value: 'beef', label: 'Говядина' },
  { value: 'pork', label: 'Свинина' },
  { value: 'fish', label: 'Рыба' },
  { value: 'seafood', label: 'Морепродукты' },
  { value: 'eggs', label: 'Яйца и молочные' },
  { value: 'veggie', label: 'Без мяса' },
];

export const COOKTIME_OPTIONS: SelectOption<ProfileCooktime>[] = [
  { value: 'fast', label: 'До 20 минут' },
  { value: 'medium', label: 'До 45 минут' },
  { value: 'slow', label: 'До 90 минут' },
];

/** Store values — backend accepts free string; default is "any". */
export const STORE_OPTIONS: SelectOption[] = [
  { value: 'any', label: 'Любой магазин' },
];

export const MEAL_TYPE_OPTIONS: SelectOption<MealType>[] = (
  ['breakfast', 'lunch', 'dinner', 'snack'] as MealType[]
).map((value) => ({
  value,
  label: MEAL_TYPE_LABELS[value],
}));

/** @deprecated Use meal_types instead. Kept for backward compatibility in storage. */
export const MEALS_PER_DAY_OPTIONS = [
  { value: 1, label: '1' },
  { value: 2, label: '2' },
  { value: 3, label: '3' },
] as const;

export const PROFILE_BUDGET = {
  min: 500,
  max: 50000,
  step: 500,
  default: 3000,
} as const;

export const PROFILE_DAYS = {
  min: 1,
  max: 7,
} as const;

export const PROFILE_PERSONS = {
  min: 1,
  max: 6,
} as const;
