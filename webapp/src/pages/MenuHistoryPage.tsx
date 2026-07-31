import { useCallback, useEffect, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';

import { getMenuHistory } from '@/api/menuHistory';
import { Button, Card, CardContent, Skeleton, Typography } from '@/components/ui';
import {
  buildHistoryItemViewModel,
  type MenuHistoryItemViewModel,
} from '@/features/menu-history/menuHistoryViewModel';
import { menuHistoryDetailPath } from '@/constants/routes';
import type { MenuHistoryItem } from '@/types/menuHistory';

const HistoryCard: FC<{ item: MenuHistoryItemViewModel; onOpen: () => void }> = ({
  item,
  onOpen,
}) => (
  <Card>
    <CardContent className="flex flex-col gap-1.5 pt-4">
      <div className="flex items-baseline justify-between gap-2">
        <Typography variant="body" className="font-semibold">
          {item.title}
        </Typography>
        <Typography
          variant="caption"
          className={item.isActive ? 'text-app-accent' : 'text-app-hint'}
        >
          {item.statusLabel}
        </Typography>
      </div>
      {item.detailsLine && (
        <Typography variant="caption" className="text-app-hint">
          {item.detailsLine}
        </Typography>
      )}
      {item.summary && (
        <Typography variant="body" className="text-app-hint">
          {item.summary}
        </Typography>
      )}
      {item.replacementsNote && (
        <Typography variant="caption" className="text-app-hint">
          {item.replacementsNote}
        </Typography>
      )}
      <Button type="button" variant="secondary" onClick={onOpen}>
        Открыть план
      </Button>
    </CardContent>
  </Card>
);

/**
 * Sprint 7.3 — read-only «История планов».
 * Shows compact summaries of durable plans stored on the backend.
 * Legacy localStorage-only plans are not listed and are never migrated.
 */
export const MenuHistoryPage: FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<MenuHistoryItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadFirstPage = useCallback(() => {
    setIsLoading(true);
    setError(null);
    getMenuHistory()
      .then((page) => {
        setItems(page.items);
        setNextCursor(page.next_cursor);
      })
      .catch(() => setError('Не удалось загрузить историю планов.'))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    loadFirstPage();
  }, [loadFirstPage]);

  const loadMore = () => {
    if (!nextCursor || isLoadingMore) return;
    setIsLoadingMore(true);
    getMenuHistory(nextCursor)
      .then((page) => {
        setItems((previous) => [...previous, ...page.items]);
        setNextCursor(page.next_cursor);
      })
      .catch(() => setError('Не удалось загрузить историю планов.'))
      .finally(() => setIsLoadingMore(false));
  };

  return (
    <div className="flex flex-col gap-4 p-4 pb-8">
      <Typography variant="caption" className="text-app-hint">
        Прошлые недельные планы хранятся на сервере и доступны только для
        просмотра.
      </Typography>
      {isLoading && (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
          <span className="sr-only">Загружаем историю планов…</span>
        </div>
      )}
      {!isLoading && error && (
        <div className="flex flex-col gap-2" role="alert">
          <Typography variant="caption" className="text-app-warning">
            {error}
          </Typography>
          <Button type="button" variant="secondary" onClick={loadFirstPage}>
            Повторить
          </Button>
        </div>
      )}
      {!isLoading && !error && items.length === 0 && (
        <Typography variant="body" className="text-app-hint">
          Пока нет сохранённых планов. Они появятся здесь после следующей
          генерации меню.
        </Typography>
      )}
      {!isLoading && items.length > 0 && (
        <ul className="flex list-none flex-col gap-3 p-0" aria-label="История планов">
          {items.map((item) => {
            const viewModel = buildHistoryItemViewModel(item);
            return (
              <li key={item.menu_plan_id}>
                <HistoryCard
                  item={viewModel}
                  onOpen={() => navigate(menuHistoryDetailPath(item.menu_plan_id))}
                />
              </li>
            );
          })}
        </ul>
      )}
      {!isLoading && nextCursor && (
        <Button
          type="button"
          variant="secondary"
          onClick={loadMore}
          disabled={isLoadingMore}
        >
          {isLoadingMore ? 'Загружаем…' : 'Показать ещё'}
        </Button>
      )}
    </div>
  );
};
