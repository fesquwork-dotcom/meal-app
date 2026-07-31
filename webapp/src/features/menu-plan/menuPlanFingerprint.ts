import type { MenuPlan } from '@/types/menu';

/** Stable session fingerprint for detecting menu plan replacement. */
export function getMenuPlanFingerprint(plan: MenuPlan): string {
  const daysKey = plan.days_plan
    .map((day) => {
      const mealsKey = day.meals
        .map((meal) => `${meal.type}:${meal.recipe_name}`)
        .join('|');
      return `${day.day}|${mealsKey}|${day.breakfast}|${day.lunch}|${day.dinner}`;
    })
    .join(';');
  const basketKey = plan.basket
    .map((category) => `${category.category}:${category.items.map((i) => `${i.name}|${i.weight}|${i.price}`).join(',')}`)
    .join(';');

  return `${plan.total_cost}|${plan.summary}|${daysKey}|${basketKey}`;
}
