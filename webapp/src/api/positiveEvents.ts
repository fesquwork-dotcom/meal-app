import { api } from '@/api/client';

/** Sprint 6.5 — explicit positive outcome events. Evidence only. */
export type PositiveEventType =
  | 'meal_cooked'
  | 'meal_suited'
  | 'shopping_completed'
  | 'plan_completed';

export type MealPositiveEventType = Extract<PositiveEventType, 'meal_cooked' | 'meal_suited'>;

export interface PositiveEventResponse {
  recorded: boolean;
  deduplicated: boolean;
}

export interface PositiveEventUndoResponse {
  removed: boolean;
  absent: boolean;
}

export async function recordPositiveEvent(
  strategyId: string,
  eventType: PositiveEventType,
  mealId?: string | null,
): Promise<PositiveEventResponse> {
  const { data } = await api.post<PositiveEventResponse>(
    `/api/strategy/${encodeURIComponent(strategyId)}/events`,
    {
      event_type: eventType,
      meal_id: mealId ?? null,
    },
  );
  return {
    recorded: data?.recorded === true,
    deduplicated: data?.deduplicated === true,
  };
}

export async function undoPositiveEvent(
  strategyId: string,
  eventType: PositiveEventType,
  mealId?: string | null,
): Promise<PositiveEventUndoResponse> {
  const { data } = await api.delete<PositiveEventUndoResponse>(
    `/api/strategy/${encodeURIComponent(strategyId)}/events`,
    {
      data: {
        event_type: eventType,
        meal_id: mealId ?? null,
      },
    },
  );
  return {
    removed: data?.removed === true,
    absent: data?.absent === true,
  };
}
