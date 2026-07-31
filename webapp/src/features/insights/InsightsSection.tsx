import { useCallback, useEffect, useState, type FC } from 'react';

import { getInsightSummary } from '@/api/insights';
import { Button, Section, Skeleton, Typography } from '@/components/ui';
import { InsightCard } from '@/features/insights/InsightCard';
import { buildInsightsViewModel } from '@/features/insights/insightsViewModel';
import type { InsightSummary } from '@/types/insights';

export const InsightsSection: FC = () => {
  const [summary, setSummary] = useState<InsightSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setIsLoading(true);
    setError(null);
    getInsightSummary()
      .then(setSummary)
      .catch(() => setError('Не удалось загрузить выводы по вашим данным.'))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    let active = true;
    getInsightSummary()
      .then((data) => {
        if (active) setSummary(data);
      })
      .catch(() => {
        if (active) setError('Не удалось загрузить выводы по вашим данным.');
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const viewModel = buildInsightsViewModel(summary);

  return (
    <Section
      title="Что означают ваши данные"
      description="Только подтверждённые выводы из итогов решений, долгосрочных трендов и изменений планов."
    >
      {isLoading && (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-28 w-full" />
          <span className="sr-only">Загружаем выводы…</span>
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
      {!isLoading && !error && viewModel && viewModel.cards.length > 0 && (
        <ul className="flex list-none flex-col gap-3 p-0" aria-label="Подтверждённые выводы">
          {viewModel.cards.map((insight) => (
            <li key={insight.id}>
              <InsightCard insight={insight} />
            </li>
          ))}
        </ul>
      )}
      {!isLoading && !error && (!viewModel || viewModel.cards.length === 0) && (
        <Typography variant="body" className="text-app-hint">
          Пока недостаточно подтверждённых данных для выводов. Здесь не появятся
          предположения — только результаты с достаточными доказательствами.
        </Typography>
      )}
    </Section>
  );
};

