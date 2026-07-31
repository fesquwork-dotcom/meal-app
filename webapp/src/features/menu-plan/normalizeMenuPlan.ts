import type { DayMeal, DayPlan, MenuPlan } from '@/types/menu';
import type { BasketCategory, BasketItem } from '@/types/basket';
import type { Recipe, RecipeIngredient, IngredientContribution } from '@/types/recipe';
import { isMealType, type MealType } from '@/types/meal';
import { normalizeDateOnly } from '@/features/menu-plan/calendar/dateHelpers';
import {
  normalizeSubstitutes,
  normalizeTips,
} from '@/features/recipes/ingredientPresentation';

function safeFiniteNumber(value: unknown, fallback = 0): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallback;
  }

  return value;
}

function normalizeOptionalCost(value: unknown): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    return null;
  }
  return value;
}

function safeString(value: unknown, fallback = ''): string {
  if (typeof value === 'string') {
    return value;
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }

  return fallback;
}

function safeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeKbju(raw: unknown): string {
  if (raw === null || raw === undefined) {
    return '';
  }

  if (typeof raw === 'string') {
    return raw;
  }

  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return String(raw);
  }

  if (typeof raw === 'object' && !Array.isArray(raw)) {
    return Object.entries(raw as Record<string, unknown>)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join(' · ');
  }

  return '';
}

function normalizeCookTime(raw: unknown): string {
  if (raw === undefined || raw === null) {
    return '';
  }

  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return `${raw} мин`;
  }

  return safeString(raw);
}

function normalizeCalories(raw: unknown): string | undefined {
  if (raw === undefined || raw === null) {
    return undefined;
  }

  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return `${raw} ккал`;
  }

  const text = safeString(raw);
  return text || undefined;
}

const VALID_CONTRIBUTIONS = new Set(['purchase', 'from_source', 'pantry']);

function normalizeContribution(raw: unknown): IngredientContribution | null | undefined {
  if (raw === null) {
    return null;
  }
  if (raw === undefined) {
    return undefined;
  }
  if (typeof raw !== 'string') {
    return undefined;
  }
  const normalized = raw.trim().toLowerCase();
  if (!VALID_CONTRIBUTIONS.has(normalized)) {
    return undefined;
  }
  return normalized as IngredientContribution;
}

function normalizeIngredient(raw: unknown): RecipeIngredient | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }

  const record = raw as Record<string, unknown>;
  const ingredient: RecipeIngredient = {
    name: safeString(record.name),
    amount: safeString(record.amount),
  };

  const contribution = normalizeContribution(record.contribution);
  if (contribution !== undefined) {
    ingredient.contribution = contribution;
  }

  return ingredient;
}

function normalizeRecipe(raw: unknown): Recipe | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }

  const record = raw as Record<string, unknown>;
  const ingredients = Array.isArray(record.ingredients)
    ? record.ingredients
        .map(normalizeIngredient)
        .filter((item): item is RecipeIngredient => item !== null)
    : [];

  const tips = normalizeTips(record.tips ?? record.tip);
  const substitutes = normalizeSubstitutes(record.substitutes);

  const recipe: Recipe = {
    name: safeString(record.name, 'Без названия'),
    emoji: safeString(record.emoji, '🍽'),
    cook_time: normalizeCookTime(record.cook_time),
    kbju: normalizeKbju(record.kbju),
    ingredients,
    steps: safeStringArray(record.steps),
    difficulty: typeof record.difficulty === 'string' ? record.difficulty : undefined,
    calories_per_portion: normalizeCalories(record.calories_per_portion),
    description: typeof record.description === 'string' ? record.description : undefined,
  };

  if (tips.length > 0) {
    recipe.tips = tips;
  }
  if (substitutes.length > 0) {
    recipe.substitutes = substitutes;
  }

  const recipeId = normalizeOptionalString(record.recipe_id);
  if (recipeId !== undefined) {
    recipe.recipe_id = recipeId;
  }

  return recipe;
}

function normalizeOptionalString(value: unknown): string | null | undefined {
  if (value === null) {
    return null;
  }
  if (value === undefined) {
    return undefined;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed || null;
  }
  return undefined;
}

function normalizeOptionalBoolean(value: unknown): boolean | null | undefined {
  if (value === null || value === undefined) {
    return value;
  }
  if (typeof value === 'boolean') {
    return value;
  }
  return undefined;
}

function normalizeOptionalPositiveInt(value: unknown): number | null | undefined {
  if (value === null || value === undefined) {
    return value;
  }
  if (typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value) && value >= 1) {
    return value;
  }
  return undefined;
}

function normalizeUsesLeftovers(value: unknown): boolean {
  if (typeof value === 'boolean') {
    return value;
  }
  return false;
}

function normalizeDayMeal(raw: unknown): DayMeal | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }

  const record = raw as Record<string, unknown>;
  const type = safeString(record.type).toLowerCase();
  const recipe_name = safeString(record.recipe_name);

  if (!isMealType(type) || !recipe_name) {
    return null;
  }

  const meal: DayMeal = {
    type,
    recipe_name,
    uses_leftovers: normalizeUsesLeftovers(record.uses_leftovers),
  };

  const mealId = normalizeOptionalString(record.meal_id);
  if (mealId !== undefined) {
    meal.meal_id = mealId;
  }

  const recipeId = normalizeOptionalString(record.recipe_id);
  if (recipeId !== undefined) {
    meal.recipe_id = recipeId;
  }

  const cookingInstanceId = normalizeOptionalString(record.cooking_instance_id);
  if (cookingInstanceId !== undefined) {
    meal.cooking_instance_id = cookingInstanceId;
  }

  const requiresCooking = normalizeOptionalBoolean(record.requires_cooking);
  if (requiresCooking !== undefined) {
    meal.requires_cooking = requiresCooking;
  }

  const preparedOnDay = normalizeOptionalPositiveInt(record.prepared_on_day);
  if (preparedOnDay !== undefined) {
    meal.prepared_on_day = preparedOnDay;
  }

  const sourceMealId = normalizeOptionalString(record.source_meal_id);
  if (sourceMealId !== undefined) {
    meal.source_meal_id = sourceMealId;
  }

  return meal;
}

function buildMealsFromLegacy(record: Record<string, unknown>): DayMeal[] {
  const legacyOrder: MealType[] = ['breakfast', 'lunch', 'dinner'];
  const meals: DayMeal[] = [];

  for (const mealType of legacyOrder) {
    const recipe_name = safeString(record[mealType]);
    if (recipe_name) {
      meals.push({ type: mealType, recipe_name, uses_leftovers: false });
    }
  }

  return meals;
}

function normalizeDayPlan(raw: unknown, index: number): DayPlan | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }

  const record = raw as Record<string, unknown>;
  const seenTypes = new Set<MealType>();
  const meals: DayMeal[] = [];

  if (Array.isArray(record.meals)) {
    for (const mealRaw of record.meals) {
      const meal = normalizeDayMeal(mealRaw);
      if (!meal || seenTypes.has(meal.type)) {
        continue;
      }
      seenTypes.add(meal.type);
      meals.push(meal);
    }
  }

  if (meals.length === 0) {
    for (const meal of buildMealsFromLegacy(record)) {
      if (seenTypes.has(meal.type)) {
        continue;
      }
      seenTypes.add(meal.type);
      meals.push(meal);
    }
  }

  const legacy = {
    breakfast: meals.find((meal) => meal.type === 'breakfast')?.recipe_name ?? '',
    lunch: meals.find((meal) => meal.type === 'lunch')?.recipe_name ?? '',
    dinner: meals.find((meal) => meal.type === 'dinner')?.recipe_name ?? '',
  };

  return {
    day: safeString(record.day, `День ${index + 1}`),
    meals,
    ...legacy,
  };
}

function normalizeStringList(raw: unknown): string[] {
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    return trimmed ? [trimmed] : [];
  }
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeBasketItem(raw: unknown): BasketItem | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }

  const record = raw as Record<string, unknown>;
  const item: BasketItem = {
    name: safeString(record.name),
    weight: safeString(record.weight),
    price: safeFiniteNumber(record.price, 0),
  };

  const usedIn = record.used_in_recipes;
  if (typeof usedIn === 'number' && Number.isFinite(usedIn) && usedIn >= 1) {
    item.used_in_recipes = Math.floor(usedIn);
  }

  const advice = normalizeStringList(record.shopping_advice);
  if (advice.length > 0) {
    item.shopping_advice = advice;
  }

  const badges = normalizeStringList(record.badges);
  if (badges.length > 0) {
    item.badges = badges;
  }

  return item;
}

function normalizeBasketCategory(raw: unknown): BasketCategory | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }

  const record = raw as Record<string, unknown>;
  const items = Array.isArray(record.items)
    ? record.items
        .map(normalizeBasketItem)
        .filter((item): item is BasketItem => item !== null)
    : [];

  return {
    category: safeString(record.category, 'Прочее'),
    items,
  };
}

function normalizeStrategyId(value: unknown): string | null | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }

  if (typeof value !== 'string') {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function normalizeRevision(value: unknown): number | undefined {
  if (
    typeof value === 'number' &&
    Number.isFinite(value) &&
    Number.isInteger(value) &&
    value >= 1
  ) {
    return value;
  }
  return undefined;
}

/**
 * Normalizes unknown menu plan payloads from API or storage.
 * Returns null for invalid or empty plans instead of throwing.
 */
export function normalizeMenuPlan(input: unknown): MenuPlan | null {
  if (input === null || input === undefined) {
    return null;
  }

  if (typeof input !== 'object' || Array.isArray(input)) {
    return null;
  }

  const raw = input as Record<string, unknown>;
  const daysPlan = Array.isArray(raw.days_plan)
    ? raw.days_plan
        .map(normalizeDayPlan)
        .filter((day): day is DayPlan => day !== null)
    : [];
  const recipes = Array.isArray(raw.recipes)
    ? raw.recipes
        .map(normalizeRecipe)
        .filter((recipe): recipe is Recipe => recipe !== null)
    : [];
  const basket = Array.isArray(raw.basket)
    ? raw.basket
        .map(normalizeBasketCategory)
        .filter((category): category is BasketCategory => category !== null)
    : [];

  if (daysPlan.length === 0 && recipes.length === 0 && basket.length === 0) {
    return null;
  }

  const plan: MenuPlan = {
    summary: safeString(raw.summary),
    plan_start_date: normalizeDateOnly(raw.plan_start_date),
    strategy_id: normalizeStrategyId(raw.strategy_id),
    total_cost: safeFiniteNumber(raw.total_cost, 0),
    days_plan: daysPlan,
    recipes,
    basket,
  };

  const budgetLimit = normalizeOptionalCost(raw.budget_limit);
  const recipeCost = normalizeOptionalCost(raw.recipe_cost);
  const shoppingCost = normalizeOptionalCost(raw.shopping_cost);
  const usagePercent = normalizeOptionalCost(raw.budget_usage_percent);
  if (budgetLimit !== null) {
    plan.budget_limit = budgetLimit;
  }
  if (recipeCost !== null) {
    plan.recipe_cost = recipeCost;
  }
  if (shoppingCost !== null) {
    plan.shopping_cost = shoppingCost;
  }
  if (usagePercent !== null) {
    plan.budget_usage_percent = usagePercent;
  }

  // Durable identity travels only as a complete pair; a plan with an id but
  // no valid revision (or vice versa) is treated as legacy.
  const menuPlanId = normalizeStrategyId(raw.menu_plan_id);
  const menuPlanRevision = normalizeRevision(raw.menu_plan_revision);
  if (menuPlanId && menuPlanRevision !== undefined) {
    plan.menu_plan_id = menuPlanId;
    plan.menu_plan_revision = menuPlanRevision;
  }

  return plan;
}
