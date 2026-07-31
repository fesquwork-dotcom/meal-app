import { useEffect, useState, type FC } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { getMenuPlanDelta, getMenuPlanDetail, getMenuPlanOriginal } from '@/api/menuHistory';
import { Button, Card, CardContent, Skeleton, Typography } from '@/components/ui';
import { VIEW_LABELS, formatHistoryDate } from '@/features/menu-history/menuHistoryViewModel';
import {
  buildPlanDeltaViewModel,
  type PlanDeltaViewModel,
} from '@/features/menu-history/planDeltaViewModel';
import { ROUTES } from '@/constants/routes';
import { MEAL_TYPE_LABELS } from '@/types/meal';
import type { MenuPlanDetail, MenuPlanView } from '@/types/menuHistory';
import type { DayPlan } from '@/types/menu';

const PlanDeltaCard: FC<{ viewModel: PlanDeltaViewModel }> = ({ viewModel }) => (
  <Card>
    <CardContent className="flex flex-col gap-1.5 pt-4">
      <Typography variant="body" className="font-semibold">
        {viewModel.title}
      </Typography>
      {!viewModel.hasChanges && (
        <Typography variant="caption" className="text-app-hint">
          Замены не изменили основные показатели плана.
        </Typography>
      )}
      <ul className="flex list-none flex-col gap-1 p-0" aria-label="Изменения плана">
        {viewModel.lines.map((line) => (
          <li key={line.id} className="flex items-baseline justify-between gap-2">
            <Typography variant="body">
              <span className="text-app-hint">{line.label}: </span>
              {line.valueLine}
            </Typography>
            {line.changeLabel && (
              <Typography variant="body" className="font-semibold">
                {line.changeLabel}
              </Typography>
            )}
          </li>
        ))}
      </ul>
    </CardContent>
  </Card>
);

const DayCard: FC<{ day: DayPlan }> = ({ day }) => (
  <Card>
    <CardContent className="flex flex-col gap-1.5 pt-4">
      <Typography variant="body" className="font-semibold">
        {day.day}
      </Typography>
      <ul className="flex list-none flex-col gap-1 p-0">
        {day.meals.map((meal, index) => (
          <li key={meal.meal_id ?? `${meal.type}-${index}`}>
            <Typography variant="body">
              <span className="text-app-hint">{MEAL_TYPE_LABELS[meal.type]}: </span>
              {meal.recipe_name}
            </Typography>
          </li>
        ))}
      </ul>
    </CardContent>
  </Card>
);

/**
 * Sprint 7.3 — read-only view of one durable plan.
 * «Текущий вариант» is the latest validated revision; «Исходный вариант» is
 * the immutable snapshot as generated. Old plans cannot be edited.
 */
export const MenuHistoryDetailPage: FC = () => {
  const { menuPlanId } = useParams<{ menuPlanId: string }>();
  const navigate = useNavigate();
  const [view, setView] = useState<MenuPlanView>('current');
  const [details, setDetails] = useState<Partial<Record<MenuPlanView, MenuPlanDetail>>>({});
  const [deltaViewModel, setDeltaViewModel] = useState<PlanDeltaViewModel | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Plan Delta (Sprint 7.4): factual original→current differences.
  // Loaded once; failures simply hide the block instead of breaking the page.
  useEffect(() => {
    if (!menuPlanId) return;
    let active = true;
    getMenuPlanDelta(menuPlanId)
      .then((result) => {
        if (active) setDeltaViewModel(buildPlanDeltaViewModel(result));
      })
      .catch(() => {
        if (active) setDeltaViewModel(null);
      });
    return () => {
      active = false;
    };
  }, [menuPlanId]);

  useEffect(() => {
    if (!menuPlanId) return;
    let active = true;
    setIsLoading(true);
    setError(null);
    const request =
      view === 'original' ? getMenuPlanOriginal(menuPlanId) : getMenuPlanDetail(menuPlanId);
    request
      .then((detail) => {
        if (!active) return;
        if (!detail) {
          setError('Не удалось загрузить план.');
          return;
        }
        setDetails((previous) => ({ ...previous, [view]: detail }));
      })
      .catch(() => {
        if (active) setError('Не удалось загрузить план.');
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [menuPlanId, view]);

  const detail = details[view];
  const startDate = detail ? formatHistoryDate(detail.plan.plan_start_date ?? null) : null;

  return (
    <div className="flex flex-col gap-4 p-4 pb-8">
      <Button type="button" variant="secondary" onClick={() => navigate(ROUTES.HISTORY)}>
        ← К истории планов
      </Button>

      {detail?.has_replacements && (
        <div
          className="flex gap-2"
          role="group"
          aria-label="Вариант плана"
        >
          {(['current', 'original'] as const).map((option) => (
            <Button
              key={option}
              type="button"
              variant={view === option ? 'default' : 'secondary'}
              aria-pressed={view === option}
              onClick={() => setView(option)}
            >
              {VIEW_LABELS[option]}
            </Button>
          ))}
        </div>
      )}

      {isLoading && !detail && (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
          <span className="sr-only">Загружаем план…</span>
        </div>
      )}

      {!isLoading && error && !detail && (
        <Typography variant="caption" className="text-app-warning" role="alert">
          {error}
        </Typography>
      )}

      {detail && (
        <div className="flex flex-col gap-3" aria-busy={isLoading}>
          <div className="flex flex-col gap-1">
            {startDate && (
              <Typography variant="body" className="font-semibold">
                План с {startDate}
              </Typography>
            )}
            <Typography variant="caption" className="text-app-hint">
              {VIEW_LABELS[detail.view]}
              {detail.has_replacements && detail.view === 'original'
                ? ' — как был сгенерирован, до замен'
                : ''}
              {' · только просмотр'}
            </Typography>
            {detail.plan.summary && (
              <Typography variant="body" className="text-app-hint">
                {detail.plan.summary}
              </Typography>
            )}
            <Typography variant="caption" className="text-app-hint">
              Стоимость корзины: {Math.round(detail.plan.total_cost)} ₽
            </Typography>
          </div>
          {deltaViewModel && <PlanDeltaCard viewModel={deltaViewModel} />}
          <ul className="flex list-none flex-col gap-3 p-0" aria-label="Дни плана">
            {detail.plan.days_plan.map((day) => (
              <li key={day.day}>
                <DayCard day={day} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
