/** Meal slot types accepted by menu generation. */
export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack';

export const VALID_MEAL_TYPES: readonly MealType[] = [
  'breakfast',
  'lunch',
  'dinner',
  'snack',
] as const;

export const DEFAULT_MEAL_TYPES: MealType[] = ['breakfast', 'lunch', 'dinner'];

export const MEAL_TYPE_LABELS: Record<MealType, string> = {
  breakfast: 'Завтрак',
  lunch: 'Обед',
  dinner: 'Ужин',
  snack: 'Перекус',
};

export function isMealType(value: string): value is MealType {
  return (VALID_MEAL_TYPES as readonly string[]).includes(value);
}

export function mealTypesFromCount(mealsPerDay: number): MealType[] {
  if (mealsPerDay <= 1) return ['breakfast'];
  if (mealsPerDay === 2) return ['breakfast', 'dinner'];
  if (mealsPerDay === 3) return ['breakfast', 'lunch', 'dinner'];
  return ['breakfast', 'lunch', 'dinner', 'snack'];
}

export function resolveMealTypes(
  mealTypes: string[] | null | undefined,
  mealsPerDay?: number | null,
): MealType[] {
  if (mealTypes && mealTypes.length > 0) {
    const resolved: MealType[] = [];
    for (const mealType of mealTypes) {
      if (isMealType(mealType) && !resolved.includes(mealType)) {
        resolved.push(mealType);
      }
    }
    if (resolved.length > 0) {
      return resolved;
    }
  }

  if (mealsPerDay != null) {
    return mealTypesFromCount(mealsPerDay);
  }

  return [...DEFAULT_MEAL_TYPES];
}

export function formatMealTypesLabel(mealTypes: MealType[]): string {
  return mealTypes.map((type) => MEAL_TYPE_LABELS[type]).join(', ');
}
