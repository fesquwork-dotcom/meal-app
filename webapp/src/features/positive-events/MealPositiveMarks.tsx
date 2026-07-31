import type { FC } from 'react';
import { Check, ThumbsUp } from 'lucide-react';
import { Typography } from '@/components/ui';
import { cn } from '@/lib/utils';
import type { MealPositiveEventType } from '@/api/positiveEvents';
import type { PositiveEventsApi } from '@/features/positive-events/usePositiveEvents';

interface MealPositiveMarksProps {
  mealId: string;
  events: PositiveEventsApi;
}

const MARK_ACTIONS: Array<{
  eventType: MealPositiveEventType;
  label: string;
  markedLabel: string;
}> = [
  { eventType: 'meal_cooked', label: 'Приготовил', markedLabel: 'Приготовлено' },
  { eventType: 'meal_suited', label: 'Понравилось', markedLabel: 'Понравилось' },
];

/** Sprint 6.5 — explicit "cooked" / "suited" marks for one meal. */
export const MealPositiveMarks: FC<MealPositiveMarksProps> = ({ mealId, events }) => {
  const cooked = events.isMarked('meal_cooked', mealId);
  const suited = events.isMarked('meal_suited', mealId);
  const status = suited ? 'Оценено' : cooked ? 'Приготовлено' : 'Запланировано';

  return (
    <div className="mt-2 flex flex-col gap-1.5">
      <Typography variant="caption" className="text-app-hint">
        {status}
      </Typography>
      <div className="flex flex-wrap gap-1.5">
        {MARK_ACTIONS.map(({ eventType, label, markedLabel }) => {
          const marked = events.isMarked(eventType, mealId);
          const pending = events.isPending(eventType, mealId);

          return (
            <button
              key={eventType}
              type="button"
              aria-pressed={marked}
              disabled={pending}
              onClick={() =>
                void (marked
                  ? events.unmark(eventType, mealId)
                  : events.mark(eventType, mealId))
              }
              className={cn(
                'inline-flex items-center gap-1 rounded-app border px-2 py-1 text-xs transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link',
                marked
                  ? 'border-transparent bg-app-secondary text-app-accent'
                  : 'border-app-secondary text-app-hint hover:bg-app-secondary hover:text-app-text',
                pending && 'opacity-60',
              )}
            >
              {marked ? (
                <Check className="h-3 w-3" aria-hidden="true" />
              ) : eventType === 'meal_suited' ? (
                <ThumbsUp className="h-3 w-3" aria-hidden="true" />
              ) : null}
              <span>{marked ? markedLabel : label}</span>
            </button>
          );
        })}
      </div>
      {suited && (
        <Typography variant="caption" className="text-app-accent" role="status">
          Учтём при следующих рекомендациях.
        </Typography>
      )}
    </div>
  );
};
