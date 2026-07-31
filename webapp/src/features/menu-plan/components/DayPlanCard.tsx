import type { FC } from 'react';
import { Apple, ChevronRight, Coffee, Moon, RefreshCw, UtensilsCrossed } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, Typography } from '@/components/ui';
import { CookingStatusBadge } from '@/features/menu-plan/components/CookingStatusBadge';
import { DayCookingSummary } from '@/features/menu-plan/components/DayCookingSummary';
import { getCookingStatus } from '@/features/menu-plan/cooking/getCookingStatus';
import type { MealsByIdIndex } from '@/features/menu-plan/cooking/types';
import { matchRecipeForMeal } from '@/features/menu-plan/matchRecipe';
import { MealPositiveMarks } from '@/features/positive-events/MealPositiveMarks';
import { calculateMealProgress } from '@/features/positive-events/mealProgress';
import type { PositiveEventsApi } from '@/features/positive-events/usePositiveEvents';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import { cn } from '@/lib/utils';
import { MEAL_TYPE_LABELS } from '@/types/meal';
import type { MealType } from '@/types/meal';
import type { DayMeal, DayPlan } from '@/types/menu';
import type { Recipe } from '@/types/recipe';

export type { MealType };

const MEAL_ICONS: Record<MealType, FC<{ className?: string }>> = {
  breakfast: Coffee,
  lunch: UtensilsCrossed,
  dinner: Moon,
  snack: Apple,
};

export interface DayPlanCardProps {
  plan: DayPlan;
  index?: number;
  recipes?: Recipe[];
  currentDayNumber?: number;
  mealsById?: MealsByIdIndex;
  showDaySummary?: boolean;
  headerSubtitle?: string;
  onOpenRecipe?: (recipeIndex: number) => void;
  onRequestMealReplacement?: (dayIndex: number, meal: DayMeal) => void;
  /** Sprint 6.5 — enables "Приготовлено" / "Подошло" marks on meals. */
  positiveEvents?: PositiveEventsApi;
}

interface MealBlockProps {
  meal: DayMeal;
  label: string;
  dayIndex: number;
  currentDayNumber: number;
  mealsById: MealsByIdIndex;
  icon: FC<{ className?: string }>;
  recipes?: Recipe[];
  onOpenRecipe?: (recipeIndex: number) => void;
  onRequestMealReplacement?: DayPlanCardProps['onRequestMealReplacement'];
  positiveEvents?: PositiveEventsApi;
}

const MealBlock: FC<MealBlockProps> = ({
  meal,
  label,
  dayIndex,
  currentDayNumber,
  mealsById,
  icon: Icon,
  recipes = [],
  onOpenRecipe,
  onRequestMealReplacement,
  positiveEvents,
}) => {
  const dish = meal.recipe_name;
  const match = matchRecipeForMeal(meal, recipes);
  const hasRecipe = match.recipeIndex !== null && match.confidence !== 'none' && onOpenRecipe;
  const cookingStatus = getCookingStatus(meal, currentDayNumber, mealsById);

  return (
    <div className="flex gap-2 rounded-app bg-app-bg p-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-app bg-app-secondary">
        <Icon className="h-4 w-4 text-app-accent" aria-hidden="true" />
      </div>

      <div className="min-w-0 flex-1">
        <Typography variant="label" className="text-app-hint">
          {label}
        </Typography>

        {hasRecipe ? (
          <button
            type="button"
            onClick={() => onOpenRecipe(match.recipeIndex as number)}
            className={cn(
              'mt-0.5 flex w-full items-center justify-between gap-2 rounded-app text-left',
              'transition-colors hover:bg-app-secondary active:bg-app-secondary',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg',
            )}
          >
            <Typography variant="body" className="break-words">
              {dish || '—'}
            </Typography>
            <span className="flex shrink-0 items-center gap-0.5 text-app-link">
              <Typography variant="caption">Рецепт</Typography>
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </span>
          </button>
        ) : (
          <Typography variant="body" className="mt-0.5 break-words">
            {dish || '—'}
          </Typography>
        )}

        <CookingStatusBadge status={cookingStatus} />

        {positiveEvents && meal.meal_id && (
          <MealPositiveMarks mealId={meal.meal_id} events={positiveEvents} />
        )}
      </div>

      {onRequestMealReplacement && meal.meal_id && (
        <button
          type="button"
          aria-label="Заменить блюдо"
          onClick={() => onRequestMealReplacement(dayIndex, meal)}
          className={cn(
            'flex h-9 shrink-0 items-center justify-center gap-1 rounded-app px-2 text-app-hint',
            'transition-colors hover:bg-app-secondary hover:text-app-text',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link',
          )}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          <span className="text-xs">Заменить</span>
        </button>
      )}
    </div>
  );
};

export const DayPlanCard: FC<DayPlanCardProps> = ({
  plan,
  index = 0,
  recipes,
  currentDayNumber,
  mealsById = {},
  showDaySummary = false,
  headerSubtitle,
  onOpenRecipe,
  onRequestMealReplacement,
  positiveEvents,
}) => {
  const prefersReducedMotion = usePrefersReducedMotion();
  const meals = plan.meals ?? [];
  const resolvedDayNumber = currentDayNumber ?? index + 1;
  const progress = positiveEvents
    ? calculateMealProgress([plan], positiveEvents)
    : null;

  const content = (
    <Card>
      <CardHeader className="flex flex-col gap-1">
        <CardTitle>{plan.day}</CardTitle>
        {headerSubtitle && (
          <Typography variant="body" className="text-app-hint">
            {headerSubtitle}
          </Typography>
        )}
        {showDaySummary && <DayCookingSummary meals={meals} />}
        {progress && progress.total > 0 && (
          <Typography variant="caption" className="text-app-hint">
            {progress.cooked} / {progress.total} приготовлено
          </Typography>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-2 pt-2">
        {meals.map((meal) => {
          const Icon = MEAL_ICONS[meal.type];

          return (
            <MealBlock
              key={`${plan.day}-${meal.type}`}
              meal={meal}
              label={MEAL_TYPE_LABELS[meal.type]}
              dayIndex={index}
              currentDayNumber={resolvedDayNumber}
              mealsById={mealsById}
              icon={Icon}
              recipes={recipes}
              onOpenRecipe={onOpenRecipe}
              onRequestMealReplacement={onRequestMealReplacement}
              positiveEvents={positiveEvents}
            />
          );
        })}
      </CardContent>
    </Card>
  );

  if (prefersReducedMotion) {
    return content;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06, ease: 'easeOut' }}
    >
      {content}
    </motion.div>
  );
};
