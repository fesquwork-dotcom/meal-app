import { useEffect, useState, type FC } from 'react';

import { getTrendSummary } from '@/api/trends';
import { Button, Card, CardContent, Section, Skeleton, Typography } from '@/components/ui';
import {
  buildTrendsViewModel,
  type TrendMetricViewModel,
} from '@/features/trends/trendsViewModel';
import type { TrendSummary } from '@/types/trends';

const TrendMetricCard: FC<{ metric: TrendMetricViewModel }> = ({ metric }) => (
  <Card>
    <CardContent className="flex flex-col gap-1.5 pt-4">
      <div className="flex items-baseline justify-between gap-2">
        <Typography variant="body">
          <span aria-hidden="true">{metric.icon} </span>
          {metric.title}
        </Typography>
        {metric.changeLabel && (
          <Typography variant="body" className="font-semibold">
            {metric.changeLabel}
          </Typography>
        )}
      </div>
      <Typography variant="caption" className="text-app-hint">
        {metric.statusLabel} · {metric.confidenceLabel}
      </Typography>
      <Typography variant="body" className="text-app-hint">
        {metric.summaryText}
      </Typography>
      <Typography variant="caption" className="text-app-hint">
        {metric.evidenceLabel} · {metric.sourceLabel}
      </Typography>
      {metric.capabilityNote && (
        <Typography variant="caption" className="text-app-hint">
          {metric.capabilityNote}
        </Typography>
      )}
    </CardContent>
  </Card>
);

export const TrendsSection: FC = () => {
  const [summary, setSummary] = useState<TrendSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setIsLoading(true);
    setError(null);
    getTrendSummary()
      .then((data) => setSummary(data))
      .catch(() => setError('Не удалось загрузить данные о прогрессе.'))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    let active = true;
    getTrendSummary()
      .then((data) => {
        if (active) setSummary(data);
      })
      .catch(() => {
        if (active) setError('Не удалось загрузить данные о прогрессе.');
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const viewModel = buildTrendsViewModel(summary);

  return (
    <Section
      title="Мой прогресс"
      description="Долгосрочные изменения по завершённым планам. Тренды ни на что не влияют — это только наблюдение."
    >
      {isLoading && (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <span className="sr-only">Загружаем данные о прогрессе…</span>
        </div>
      )}
      {!isLoading && error && (
        <div className="flex flex-col gap-2" role="alert">
          <Typography variant="caption" className="text-app-warning">
            {error}
          </Typography>
          <Button type="button" variant="secondary" onClick={load}>
            Повторить
          </Button>
        </div>
      )}
      {!isLoading && !error && viewModel && (
        <div className="flex flex-col gap-3">
          <Typography variant="caption" className="text-app-hint" role="status">
            Общая уверенность: {viewModel.overallLabel.toLowerCase()}
          </Typography>
          <ul className="flex list-none flex-col gap-3 p-0" aria-label="Метрики прогресса">
            {viewModel.metrics.map((metric) => (
              <li key={metric.id}>
                <TrendMetricCard metric={metric} />
              </li>
            ))}
          </ul>
        </div>
      )}
      {!isLoading && !error && !viewModel && (
        <Typography variant="body" className="text-app-hint">
          Пока недостаточно данных. Завершите хотя бы несколько недельных планов,
          и здесь появится ваша динамика.
        </Typography>
      )}
    </Section>
  );
};
