import type { FC } from 'react';
import { Check } from 'lucide-react';
import { Button, Card, CardContent, Typography } from '@/components/ui';
import type { PositiveEventType } from '@/api/positiveEvents';
import type { PositiveEventsApi } from '@/features/positive-events/usePositiveEvents';

interface PositiveEventCardProps {
  eventType: Extract<PositiveEventType, 'shopping_completed' | 'plan_completed'>;
  title: string;
  description: string;
  actionLabel: string;
  markedLabel: string;
  events: PositiveEventsApi;
}

/** Sprint 6.5 — one-tap strategy-scoped mark ("закупка выполнена", "план завершён"). */
export const PositiveEventCard: FC<PositiveEventCardProps> = ({
  eventType,
  title,
  description,
  actionLabel,
  markedLabel,
  events,
}) => {
  const marked = events.isMarked(eventType);
  const pending = events.isPending(eventType);

  return (
    <Card>
      <CardContent className="flex flex-col gap-2 pt-4">
        <Typography variant="h3">{title}</Typography>
        {marked ? (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-app-accent" role="status">
              <Check className="h-4 w-4" aria-hidden="true" />
              <Typography variant="body">{markedLabel}</Typography>
            </div>
            <Button
              type="button"
              size="full"
              variant="ghost"
              disabled={pending}
              onClick={() => void events.unmark(eventType)}
            >
              Отменить
            </Button>
          </div>
        ) : (
          <>
            <Typography variant="body" className="text-app-hint">
              {description}
            </Typography>
            <Button
              type="button"
              size="full"
              variant="secondary"
              disabled={pending}
              onClick={() => void events.mark(eventType)}
            >
              {actionLabel}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
};
