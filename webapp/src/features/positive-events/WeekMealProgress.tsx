import type { FC } from 'react';
import { Card, CardContent, Typography } from '@/components/ui';
import type { MealProgress } from '@/features/positive-events/mealProgress';

interface WeekMealProgressProps {
  progress: MealProgress;
  planCompleted: boolean;
}

export const WeekMealProgress: FC<WeekMealProgressProps> = ({
  progress,
  planCompleted,
}) => {
  const complete = progress.complete || planCompleted;
  const fill = progress.total > 0 ? (progress.cooked / progress.total) * 100 : 0;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-4">
        <Typography variant="h3">{complete ? 'Неделя завершена' : 'Неделя'}</Typography>
        <div
          className="h-2 overflow-hidden rounded-full bg-app-secondary"
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
        <Typography variant="body" className="text-app-hint">
          {progress.cooked} из {progress.total} блюд приготовлено
        </Typography>
        {complete && (
          <div className="flex flex-col gap-1" role="status">
            <Typography variant="label">Спасибо!</Typography>
            <Typography variant="body" className="text-app-hint">
              Эти данные помогут приложению лучше подбирать меню.
            </Typography>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
