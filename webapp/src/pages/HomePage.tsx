import { useEffect, useRef, type CSSProperties, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  InlineError,
  MenuPlanLoadingSkeleton,
  Section,
  Skeleton,
  Spinner,
  Typography,
} from '@/components/ui';
import { AnimatedCard } from '@/features/home/AnimatedCard';
import { HomeStrategyContextCard } from '@/features/home/HomeStrategyContextCard';
import { buildHomeStrategyContextViewModel } from '@/features/home/homeStrategyContextViewModel';
import { buildAsyncResourceViewModel } from '@/features/async-resource';
import { StrategyWorkflowErrorPanel } from '@/features/strategy-workflow';
import { useCurrentStrategy } from '@/hooks/useCurrentStrategy';
import { useGenerateMenuSheet } from '@/features/menu-generator/GenerateMenuSheetContext';
import { getHomePlanHeader, getPlanDayState } from '@/features/menu-plan/calendar/planDayState';
import { DayPlanCard } from '@/features/menu-plan/components/DayPlanCard';
import { canReplaceMeal } from '@/features/menu-plan/canReplaceMeal';
import { useReplaceMealSheet } from '@/features/menu-plan/ReplaceMealSheetContext';
import { useMealsById } from '@/features/menu-plan/useMealsById';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import { usePositiveEvents } from '@/features/positive-events/usePositiveEvents';
import { GOAL_OPTIONS, PROTEIN_OPTIONS } from '@/features/profile/constants';
import { formatMealTypesLabel } from '@/types/meal';
import { useProfile } from '@/features/profile/ProfileProvider';
import { useGreeting } from '@/hooks/useGreeting';
import { getDisplayFirstName } from '@/lib/telegram';
import { recipeDetailPath, ROUTES } from '@/constants/routes';
import { formatCurrency } from '@/utils/formatCurrency';
import { pluralForm, pluralize } from '@/utils/pluralize';

interface BudgetProgressProps {
  spent: number;
  total: number;
}

const BudgetProgress: FC<BudgetProgressProps> = ({ spent, total }) => {
  const percent = total > 0 ? Math.min(Math.round((spent / total) * 100), 100) : 0;

  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-app-bg"
      role="progressbar"
      aria-valuenow={spent}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-label={`Стоимость меню ${percent}% от бюджета`}
    >
      <div
        className="h-full rounded-full bg-app-button transition-all [width:var(--budget-progress)]"
        style={{ '--budget-progress': `${percent}%` } as CSSProperties}
      />
    </div>
  );
};

function getGoalLabel(goal: string): string {
  return GOAL_OPTIONS.find((option) => option.value === goal)?.label ?? goal;
}

function getProteinLabels(proteins: string[]): string {
  return proteins
    .map((protein) => PROTEIN_OPTIONS.find((option) => option.value === protein)?.label ?? protein)
    .join(', ');
}

export const HomePage: FC = () => {
  const navigate = useNavigate();
  const greeting = useGreeting();
  const { openSheet } = useGenerateMenuSheet();
  const {
    profile,
    isProfileLoaded,
    isLoading: isProfileLoading,
    error: profileError,
    reloadProfile,
    ensureFreshProfile,
  } = useProfile();

  useEffect(() => {
    void ensureFreshProfile();
  }, [ensureFreshProfile]);
  const { menuPlan, isMenuPlanHydrated, isGenerating } = useMenuPlan();

  // Current Strategy = lifecycle/metadata only. The displayed menu always comes
  // from the local MenuPlan; strategy status none/404 never deletes it.
  const currentStrategy = useCurrentStrategy();
  const strategyViewModel = buildAsyncResourceViewModel(
    currentStrategy.resource,
    currentStrategy.freshness,
  );
  const strategyContext = buildHomeStrategyContextViewModel(currentStrategy.data, new Date());
  const prevStrategyStatusRef = useRef(currentStrategy.resource.status);
  useEffect(() => {
    const previous = prevStrategyStatusRef.current;
    const next = currentStrategy.resource.status;
    prevStrategyStatusRef.current = next;
    if (!import.meta.env.DEV || previous === next) {
      return;
    }
    if (next === 'refreshing' || next === 'loading') {
      console.info('home_strategy_refresh_started', { hadMenuPlan: menuPlan !== null });
    }
    if (next === 'error' && menuPlan !== null) {
      console.info('home_strategy_refresh_failed_with_menu', { hadMenuPlan: true });
    }
  }, [currentStrategy.resource.status, menuPlan]);
  const { openSheet: openReplaceSheet } = useReplaceMealSheet();
  const mealsById = useMealsById(menuPlan);
  const replacementEnabled = canReplaceMeal(menuPlan);
  const positiveEvents = usePositiveEvents(menuPlan?.strategy_id);

  const displayName = getDisplayFirstName(profile);
  const greetingLine = displayName ? `${greeting}, ${displayName}!` : `${greeting}!`;

  const planDayState = menuPlan
    ? getPlanDayState({
        planStartDate: menuPlan.plan_start_date,
        planLength: menuPlan.days_plan.length,
        currentDate: new Date(),
      })
    : null;
  const activeDayIndex = planDayState?.kind === 'active' ? planDayState.dayIndex : 0;
  const todayPlan =
    menuPlan && (planDayState?.kind === 'active' || planDayState?.kind === 'legacy' || planDayState?.kind === 'invalid')
      ? menuPlan.days_plan[activeDayIndex]
      : null;
  const planHeader = planDayState ? getHomePlanHeader(planDayState) : null;
  const budgetTotal = profile?.budget ?? menuPlan?.total_cost ?? 0;
  const menuCost = menuPlan?.total_cost ?? 0;
  const remaining = Math.max(budgetTotal - menuCost, 0);

  const canOpenSheet = isProfileLoaded && profile !== null;

  const isGenerateDisabled = !canOpenSheet || isProfileLoading || isGenerating;

  const handleGenerateClick = () => {
    if (profileError && !profile) {
      navigate(ROUTES.PROFILE);
      return;
    }
    if (canOpenSheet) {
      openSheet();
    }
  };

  const handleOpenRecipe = (recipeIndex: number) => {
    navigate(recipeDetailPath(recipeIndex));
  };

  if (!isMenuPlanHydrated) {
    return <MenuPlanLoadingSkeleton />;
  }

  return (
    <div className="flex flex-col gap-6 p-4">
      <Section>
        <Typography variant="h1">{greetingLine}</Typography>
        <Typography variant="body" className="text-app-hint">
          {menuPlan?.summary || 'Вот ваш план на сегодня'}
        </Typography>
      </Section>

      {profileError && !profile && (
        <InlineError message={profileError.message} onRetry={() => void reloadProfile()}>
          <Button type="button" variant="ghost" className="mt-2" onClick={() => navigate(ROUTES.PROFILE)}>
            Перейти в профиль
          </Button>
        </InlineError>
      )}

      {profileError && profile && (
        <InlineError message={profileError.message} onRetry={() => void reloadProfile()}>
          <Typography variant="caption" className="text-app-hint">
            Не удалось обновить данные. Показана ранее загруженная версия.
          </Typography>
        </InlineError>
      )}

      {menuPlan && strategyViewModel.showRefreshingIndicator && (
        <Typography variant="caption" className="text-app-hint" aria-live="polite">
          Проверяем актуальность плана…
        </Typography>
      )}

      {menuPlan && currentStrategy.error && !strategyViewModel.showRefreshingIndicator && (
        <div className="flex flex-col gap-1" role="status">
          <Typography variant="caption" className="text-app-hint">
            Не удалось проверить актуальность плана. Меню показано из сохранённой версии.
          </Typography>
          {strategyViewModel.retryEnabled && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="self-start"
              onClick={() => void currentStrategy.reload()}
            >
              Повторить
            </Button>
          )}
        </div>
      )}

      {!menuPlan && strategyViewModel.showFullError && currentStrategy.error && (
        <StrategyWorkflowErrorPanel
          error={currentStrategy.error}
          variant="compact"
          onRetry={
            strategyViewModel.retryEnabled ? () => void currentStrategy.reload() : undefined
          }
        />
      )}

      {menuPlan && (
        <AnimatedCard delay={0.02}>
          <Card>
            <CardContent className="flex flex-col gap-3 pt-4">
              <div className="flex items-end justify-between">
                <div>
                  <Typography variant="caption" className="text-app-hint">
                    Стоимость меню
                  </Typography>
                  <Typography variant="h2" className="text-app-accent">
                    {formatCurrency(menuPlan.total_cost)}
                  </Typography>
                </div>
                <div className="text-right">
                  <Typography variant="caption" className="text-app-hint">
                    {pluralForm(menuPlan.days_plan.length, ['день', 'дня', 'дней'])}
                  </Typography>
                  <Typography variant="h3">{menuPlan.days_plan.length}</Typography>
                </div>
              </div>
              {profile && budgetTotal > 0 && (
                <>
                  <BudgetProgress spent={menuCost} total={budgetTotal} />
                  <Typography variant="caption" className="text-app-hint">
                    Остаток бюджета {formatCurrency(remaining)}
                  </Typography>
                </>
              )}
            </CardContent>
          </Card>
        </AnimatedCard>
      )}

      {menuPlan && strategyContext.visible && (
        <AnimatedCard delay={0.03}>
          <HomeStrategyContextCard
            viewModel={strategyContext}
            onOpenDetails={() => navigate(ROUTES.WEEK)}
          />
        </AnimatedCard>
      )}

      {isProfileLoaded && profile && !menuPlan && (
        <AnimatedCard delay={0.03}>
          <Card>
            <CardHeader>
              <CardTitle>Ваши настройки</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 pt-2">
              <Typography variant="body">
                <span className="text-app-hint">Цель: </span>
                {getGoalLabel(profile.goal)}
              </Typography>
              <Typography variant="body">
                <span className="text-app-hint">Основные продукты: </span>
                {getProteinLabels(profile.proteins)}
              </Typography>
              <Typography variant="body">
                <span className="text-app-hint">План: </span>
                {profile.days} дн. · {profile.persons} чел.
              </Typography>
              <Typography variant="body">
                <span className="text-app-hint">Приёмы пищи: </span>
                {formatMealTypesLabel(profile.meal_types)}
              </Typography>
            </CardContent>
          </Card>
        </AnimatedCard>
      )}

      {!isProfileLoaded && !profileError && !menuPlan && (
        <Card>
          <CardContent className="flex flex-col gap-2 pt-4">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </CardContent>
        </Card>
      )}

      {menuPlan && todayPlan && planHeader && (
        <DayPlanCard
          plan={{ ...todayPlan, day: planHeader.title }}
          index={activeDayIndex}
          currentDayNumber={activeDayIndex + 1}
          mealsById={mealsById}
          showDaySummary
          headerSubtitle={planHeader.subtitle}
          recipes={menuPlan.recipes}
          onOpenRecipe={handleOpenRecipe}
          onRequestMealReplacement={
            replacementEnabled
              ? (dayIndex, meal) => openReplaceSheet({ dayIndex, meal })
              : undefined
          }
          positiveEvents={menuPlan.strategy_id ? positiveEvents : undefined}
        />
      )}

      {menuPlan && planDayState?.kind === 'before_start' && planHeader && (
        <AnimatedCard delay={0.05}>
          <Card>
            <CardHeader>
              <CardTitle>{planHeader.title}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 pt-2">
              {planHeader.subtitle && (
                <Typography variant="body" className="text-app-hint">
                  {planHeader.subtitle}
                </Typography>
              )}
              {menuPlan.days_plan[0] && (
                <Button type="button" variant="secondary" onClick={() => navigate(ROUTES.WEEK)}>
                  Посмотреть первый день
                </Button>
              )}
            </CardContent>
          </Card>
        </AnimatedCard>
      )}

      {menuPlan && planDayState?.kind === 'completed' && planHeader && (
        <AnimatedCard delay={0.05}>
          <Card>
            <CardHeader>
              <CardTitle>{planHeader.title}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 pt-2">
              {planHeader.subtitle && (
                <Typography variant="body" className="text-app-hint">
                  {planHeader.subtitle}
                </Typography>
              )}
              <Button type="button" variant="secondary" onClick={openSheet}>
                Создать новый план
              </Button>
              <Button type="button" variant="ghost" onClick={() => navigate(ROUTES.WEEK)}>
                Посмотреть прошлый план
              </Button>
            </CardContent>
          </Card>
        </AnimatedCard>
      )}

      {!menuPlan && isMenuPlanHydrated && (
        <AnimatedCard delay={0.05}>
          <Card>
            <CardHeader>
              <CardTitle>Сегодня</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <Typography variant="body" className="text-app-hint">
                Создайте меню, чтобы увидеть блюда на сегодня.
              </Typography>
            </CardContent>
          </Card>
        </AnimatedCard>
      )}

      {menuPlan && (
        <AnimatedCard delay={0.1}>
          <div className="grid grid-cols-3 gap-2">
            <Button type="button" variant="secondary" onClick={() => navigate(ROUTES.WEEK)}>
              Вся неделя
            </Button>
            <Button type="button" variant="secondary" onClick={() => navigate(ROUTES.RECIPES)}>
              Рецепты
            </Button>
            <Button type="button" variant="secondary" onClick={() => navigate(ROUTES.BASKET)}>
              Корзина
            </Button>
          </div>
        </AnimatedCard>
      )}

      {!menuPlan && isProfileLoaded && profile && (
        <AnimatedCard delay={0.15}>
          <Card>
            <CardHeader>
              <CardTitle>Бюджет</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <Typography variant="h2">{formatCurrency(profile.budget)}</Typography>
              <Typography variant="caption" className="text-app-hint">
                {pluralize(profile.days, ['день', 'дня', 'дней'])} · {profile.persons} чел.
              </Typography>
            </CardContent>
          </Card>
        </AnimatedCard>
      )}

      <AnimatedCard delay={0.2}>
        <Button
          size="full"
          type="button"
          disabled={isGenerateDisabled}
          onClick={handleGenerateClick}
        >
          {isGenerating ? (
            <span className="inline-flex items-center gap-2">
              <Spinner size="sm" />
              Создаём меню…
            </span>
          ) : (
            'Сгенерировать новую неделю'
          )}
        </Button>
      </AnimatedCard>
    </div>
  );
};
