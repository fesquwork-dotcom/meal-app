import {
  useLayoutEffect,
  useRef,
  useState,
  type FC,
} from 'react';
import { Card, CardContent, Typography } from '@/components/ui';
import type { MealProgress } from '@/features/positive-events/mealProgress';
import { formatCurrency } from '@/utils/formatCurrency';
import { pluralForm } from '@/utils/pluralize';

export interface WeekHeaderProps {
  summary: string;
  totalCost: number;
  dayCount: number;
  recipeCount: number;
  basketItemCount: number;
  progress: MealProgress;
  planCompleted: boolean;
  showProgress: boolean;
  onOpenSettings: () => void;
  /** Sprint 10.5.4 — hide block when shopping cost / budget unknown. */
  budgetLimit?: number | null;
  shoppingCost?: number | null;
  budgetUsagePercent?: number | null;
}

/**
 * Compact week summary: description, cost, progress, stats and settings link
 * in a single card so Day 1 can sit near the first viewport.
 */
export const WeekHeader: FC<WeekHeaderProps> = ({
  summary,
  totalCost,
  dayCount,
  recipeCount,
  basketItemCount,
  progress,
  planCompleted,
  showProgress,
  onOpenSettings,
  budgetLimit,
  shoppingCost,
  budgetUsagePercent,
}) => {
  const complete = progress.complete || planCompleted;
  const fill = progress.total > 0 ? (progress.cooked / progress.total) * 100 : 0;
  const trimmedSummary = summary.trim();

  const statsLine = [
    `${dayCount} ${pluralForm(dayCount, ['день', 'дня', 'дней'])}`,
    `${recipeCount} ${pluralForm(recipeCount, ['рецепт', 'рецепта', 'рецептов'])}`,
    `${basketItemCount} в корзине`,
  ].join(' · ');

  const showBudgetUsage =
    typeof budgetLimit === 'number' &&
    budgetLimit > 0 &&
    typeof shoppingCost === 'number' &&
    shoppingCost >= 0 &&
    typeof budgetUsagePercent === 'number' &&
    Number.isFinite(budgetUsagePercent);

  const usageFill = showBudgetUsage
    ? Math.min(Math.max(budgetUsagePercent, 0), 100)
    : 0;

  return (
    <Card data-testid="week-header" aria-label="Сводка недели">
      <CardContent className="flex flex-col gap-3 p-4">
        <Typography variant="h2" className="text-base font-semibold leading-tight">
          План на неделю
        </Typography>

        {trimmedSummary ? <ExpandableSummary text={trimmedSummary} /> : null}

        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
          <Typography
            variant="h2"
            className="min-w-0 shrink-0 break-words text-app-accent"
          >
            {formatCurrency(totalCost)}
          </Typography>

          {showProgress ? (
            <div className="flex min-w-0 flex-1 flex-col gap-1.5 sm:max-w-xs sm:items-end">
              <Typography variant="caption" className="text-app-hint sm:text-right">
                {complete
                  ? 'Неделя завершена'
                  : `${progress.cooked} из ${progress.total} приготовлено`}
              </Typography>
              <div
                className="h-1.5 w-full overflow-hidden rounded-full bg-app-bg"
                role="progressbar"
                aria-label="Прогресс недели"
                aria-valuemin={0}
                aria-valuemax={progress.total}
                aria-valuenow={progress.cooked}
              >
                <div
                  className="h-full rounded-full bg-app-button transition-[width]"
                  style={{ width: `${fill}%` }}
                />
              </div>
            </div>
          ) : null}
        </div>

        {showBudgetUsage ? (
          <div
            className="flex flex-col gap-1.5"
            data-testid="week-budget-usage"
            aria-label="Использовано бюджета"
          >
            <Typography variant="caption" className="text-app-hint">
              Использовано бюджета
            </Typography>
            <div
              className="h-1.5 w-full overflow-hidden rounded-full bg-app-bg"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(usageFill)}
              aria-label={`Использовано ${Math.round(usageFill)} процентов бюджета`}
            >
              <div
                className="h-full rounded-full bg-app-accent/80 transition-[width]"
                style={{ width: `${usageFill}%` }}
              />
            </div>
            <Typography variant="caption" className="tabular-nums text-app-subtitle">
              {formatCurrency(shoppingCost)} / {formatCurrency(budgetLimit)} ·{' '}
              {Number.isInteger(budgetUsagePercent)
                ? `${budgetUsagePercent}%`
                : `${budgetUsagePercent.toFixed(1)}%`}
            </Typography>
          </div>
        ) : null}

        <Typography variant="caption" className="text-app-hint">
          {statsLine}
        </Typography>

        <button
          type="button"
          className="min-h-11 w-full rounded-app px-0 py-1 text-left text-sm leading-snug text-app-link underline-offset-2 hover:underline"
          onClick={onOpenSettings}
        >
          Изменили настройки?
          <br />
          Посмотреть, как изменится следующий план
        </button>
      </CardContent>
    </Card>
  );
};

function ExpandableSummary({ text }: { text: string }) {
  const textRef = useRef<HTMLParagraphElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [canExpand, setCanExpand] = useState(false);

  useLayoutEffect(() => {
    if (expanded) {
      return;
    }
    const node = textRef.current;
    if (!node) {
      return;
    }
    // Detect overflow only while clamped; short copy must not show a toggle.
    setCanExpand(node.scrollHeight > node.clientHeight + 1);
  }, [text, expanded]);

  return (
    <div className="flex flex-col gap-1">
      <p
        ref={textRef}
        className={
          expanded
            ? 'text-base font-normal text-app-hint'
            : 'line-clamp-4 text-base font-normal text-app-hint'
        }
      >
        {text}
      </p>
      {canExpand || expanded ? (
        <button
          type="button"
          className="min-h-10 self-start text-left text-sm text-app-link underline-offset-2 hover:underline"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'Свернуть' : 'Показать полностью'}
        </button>
      ) : null}
    </div>
  );
}
