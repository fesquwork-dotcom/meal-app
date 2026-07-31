import type { FC } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  EmptyState,
  MenuPlanLoadingSkeleton,
} from '@/components/ui';
import { countBasketItems } from '@/features/basket';
import { useGenerateMenuSheet } from '@/features/menu-generator/GenerateMenuSheetContext';
import { getPlanDayState, getPlanDayTitle } from '@/features/menu-plan/calendar/planDayState';
import { StrategyExplanationBlock } from '@/features/strategy/StrategyExplanationBlock';
import { buildBudgetUtilizationText } from '@/features/strategy/budgetUtilizationCopy';
import { AppliedPlanSettingsBlock } from '@/features/strategy/AppliedPlanSettingsBlock';
import { DayPlanCard } from '@/features/menu-plan/components/DayPlanCard';
import { WeekHeader } from '@/features/menu-plan/components/WeekHeader';
import { PositiveEventCard } from '@/features/positive-events/PositiveEventCard';
import { calculateMealProgress } from '@/features/positive-events/mealProgress';
import { usePositiveEvents } from '@/features/positive-events/usePositiveEvents';
import { canReplaceMeal, explainReplaceMealAvailability } from '@/features/menu-plan/canReplaceMeal';
import { useReplaceMealSheet } from '@/features/menu-plan/ReplaceMealSheetContext';
import { useMealsById } from '@/features/menu-plan/useMealsById';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import { recipeDetailPath, ROUTES } from '@/constants/routes';

export const WeekPage: FC = () => {
  const navigate = useNavigate();
  const { menuPlan, isMenuPlanHydrated } = useMenuPlan();
  const mealsById = useMealsById(menuPlan);
  const { openSheet } = useGenerateMenuSheet();
  const { openSheet: openReplaceSheet } = useReplaceMealSheet();
  const replacementEnabled = canReplaceMeal(menuPlan);
  if (import.meta.env.DEV && menuPlan && !replacementEnabled) {
    console.info(
      '[replace-button] hidden:',
      explainReplaceMealAvailability(menuPlan).reasons,
    );
  }
  const positiveEvents = usePositiveEvents(menuPlan?.strategy_id);
  const positiveEventsEnabled = Boolean(menuPlan?.strategy_id);

  const handleOpenRecipe = (recipeIndex: number) => {
    navigate(recipeDetailPath(recipeIndex));
  };

  if (!isMenuPlanHydrated) {
    return <MenuPlanLoadingSkeleton />;
  }

  if (!menuPlan) {
    return (
      <div className="p-4">
        <EmptyState
          title="Меню ещё не создано"
          description="Сгенерируйте план питания на главной странице, чтобы увидеть расписание на неделю."
          actionLabel="На главную"
          onAction={() => navigate(ROUTES.HOME)}
        />
      </div>
    );
  }

  const basketItemCount = countBasketItems(menuPlan.basket);
  const recipeCount = menuPlan.recipes.length;
  const dayCount = menuPlan.days_plan.length;
  const planDayState = getPlanDayState({
    planStartDate: menuPlan.plan_start_date,
    planLength: dayCount,
    currentDate: new Date(),
  });
  const currentDayIndex = planDayState.kind === 'active' ? planDayState.dayIndex : null;
  const dayLabels = menuPlan.days_plan.map((day, dayIndex) =>
    getPlanDayTitle(day.day, dayIndex, menuPlan.plan_start_date),
  );
  const weekProgress = calculateMealProgress(menuPlan.days_plan, positiveEvents);
  const planCompleted = positiveEvents.isMarked('plan_completed');
  const budgetUtilizationText = buildBudgetUtilizationText({
    budgetLimit: menuPlan.budget_limit,
    shoppingCost: menuPlan.shopping_cost ?? menuPlan.total_cost,
    recipeCost: menuPlan.recipe_cost,
    budgetUsagePercent: menuPlan.budget_usage_percent,
  });

  if (dayCount === 0) {
    return (
      <div className="p-4">
        <EmptyState
          title="План дней пуст"
          description="Сервер не вернул расписание по дням. Попробуйте создать меню заново."
          actionLabel="Создать другое меню"
          onAction={openSheet}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4 pb-8">
      <WeekHeader
        summary={menuPlan.summary ?? ''}
        totalCost={menuPlan.total_cost}
        dayCount={dayCount}
        recipeCount={recipeCount}
        basketItemCount={basketItemCount}
        progress={weekProgress}
        planCompleted={planCompleted}
        showProgress={positiveEventsEnabled}
        onOpenSettings={() => navigate(ROUTES.PROFILE)}
        budgetLimit={menuPlan.budget_limit}
        shoppingCost={menuPlan.shopping_cost ?? menuPlan.total_cost}
        budgetUsagePercent={menuPlan.budget_usage_percent}
      />

      <div className="flex flex-col gap-3">
        {menuPlan.days_plan.map((day, dayIndex) => {
          const isCurrentDay = currentDayIndex === dayIndex;
          const title = isCurrentDay ? `${dayLabels[dayIndex]} · Сегодня` : dayLabels[dayIndex];

          return (
            <div key={`${day.day}-${dayIndex}`} aria-current={isCurrentDay ? 'date' : undefined}>
              <DayPlanCard
                plan={{ ...day, day: title }}
                index={dayIndex}
                currentDayNumber={dayIndex + 1}
                mealsById={mealsById}
                recipes={menuPlan.recipes}
                onOpenRecipe={handleOpenRecipe}
                onRequestMealReplacement={
                  replacementEnabled
                    ? (dayIndex, meal) => openReplaceSheet({ dayIndex, meal })
                    : undefined
                }
                positiveEvents={positiveEventsEnabled ? positiveEvents : undefined}
              />
            </div>
          );
        })}
      </div>

      {positiveEventsEnabled && planDayState.kind !== 'before_start' && (
        <PositiveEventCard
          eventType="plan_completed"
          title={weekProgress.complete ? 'Все блюда приготовлены' : 'Завершить неделю'}
          description={
            weekProgress.complete
              ? 'Подтвердите завершение недели — эти данные помогут улучшить следующие рекомендации.'
              : 'Можно завершить план вручную, если вы больше не будете готовить блюда этой недели.'
          }
          actionLabel="Завершить неделю"
          markedLabel="Неделя отмечена завершённой"
          events={positiveEvents}
        />
      )}

      {/* Secondary strategy context lives below the menu: the week's meals are the
          primary content of the first screen. */}
      <StrategyExplanationBlock
        strategyId={menuPlan.strategy_id}
        budgetUtilizationText={budgetUtilizationText}
      />

      <AppliedPlanSettingsBlock strategyId={menuPlan.strategy_id} />

      <div className="flex flex-col gap-2">
        <Button type="button" size="full" variant="secondary" onClick={openSheet}>
          Создать другое меню
        </Button>
        <Button type="button" size="full" variant="ghost" onClick={() => navigate(ROUTES.RECIPES)}>
          Перейти к рецептам
        </Button>
        <Button type="button" size="full" variant="ghost" onClick={() => navigate(ROUTES.BASKET)}>
          Открыть корзину
        </Button>
      </div>
    </div>
  );
};
