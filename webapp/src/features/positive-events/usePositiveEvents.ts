import { useCallback, useMemo, useRef, useState } from 'react';
import {
  recordPositiveEvent,
  undoPositiveEvent,
  type PositiveEventType,
} from '@/api/positiveEvents';
import {
  buildMarkKey,
  loadPositiveEventMarks,
  persistPositiveEventMarks,
} from '@/features/positive-events/positiveEventMarks';

export interface PositiveEventsApi {
  /** True when this mark was already sent (locally or in a previous session). */
  isMarked: (eventType: PositiveEventType, mealId?: string | null) => boolean;
  /** True while the mark request is in flight. */
  isPending: (eventType: PositiveEventType, mealId?: string | null) => boolean;
  /** Sends the event once; failures re-enable the action for a retry. */
  mark: (eventType: PositiveEventType, mealId?: string | null) => Promise<void>;
  /** Removes one explicit mark; failures restore the previous UI state. */
  unmark: (eventType: PositiveEventType, mealId?: string | null) => Promise<void>;
}

/**
 * Sprint 6.5 — client side of explicit positive outcome events.
 * The backend deduplicates by a server-derived key, so a lost local mark
 * only causes a harmless repeated request.
 */
export function usePositiveEvents(strategyId: string | null | undefined): PositiveEventsApi {
  const [marks, setMarks] = useState<Set<string>>(() =>
    strategyId ? loadPositiveEventMarks(strategyId) : new Set(),
  );
  const [pending, setPending] = useState<Set<string>>(new Set());
  const inFlightRef = useRef<Set<string>>(new Set());
  const loadedStrategyRef = useRef<string | null | undefined>(strategyId);

  if (loadedStrategyRef.current !== strategyId) {
    loadedStrategyRef.current = strategyId;
    setMarks(strategyId ? loadPositiveEventMarks(strategyId) : new Set());
    setPending(new Set());
    inFlightRef.current.clear();
  }

  const isMarked = useCallback(
    (eventType: PositiveEventType, mealId?: string | null) =>
      marks.has(buildMarkKey(eventType, mealId)),
    [marks],
  );

  const isPending = useCallback(
    (eventType: PositiveEventType, mealId?: string | null) =>
      pending.has(buildMarkKey(eventType, mealId)),
    [pending],
  );

  const mark = useCallback(
    async (eventType: PositiveEventType, mealId?: string | null) => {
      if (!strategyId) {
        return;
      }
      const key = buildMarkKey(eventType, mealId);
      if (marks.has(key) || inFlightRef.current.has(key)) {
        return;
      }
      inFlightRef.current.add(key);
      setPending((current) => new Set(current).add(key));
      setMarks((current) => {
        const next = new Set(current).add(key);
        persistPositiveEventMarks(strategyId, next);
        return next;
      });
      try {
        await recordPositiveEvent(strategyId, eventType, mealId);
      } catch {
        setMarks((current) => {
          const next = new Set(current);
          next.delete(key);
          persistPositiveEventMarks(strategyId, next);
          return next;
        });
      } finally {
        inFlightRef.current.delete(key);
        setPending((current) => {
          const next = new Set(current);
          next.delete(key);
          return next;
        });
      }
    },
    [strategyId, marks],
  );

  const unmark = useCallback(
    async (eventType: PositiveEventType, mealId?: string | null) => {
      if (!strategyId) {
        return;
      }
      const key = buildMarkKey(eventType, mealId);
      if (!marks.has(key) || inFlightRef.current.has(key)) {
        return;
      }
      inFlightRef.current.add(key);
      setPending((current) => new Set(current).add(key));
      setMarks((current) => {
        const next = new Set(current);
        next.delete(key);
        persistPositiveEventMarks(strategyId, next);
        return next;
      });
      try {
        await undoPositiveEvent(strategyId, eventType, mealId);
      } catch {
        setMarks((current) => {
          const next = new Set(current).add(key);
          persistPositiveEventMarks(strategyId, next);
          return next;
        });
      } finally {
        inFlightRef.current.delete(key);
        setPending((current) => {
          const next = new Set(current);
          next.delete(key);
          return next;
        });
      }
    },
    [strategyId, marks],
  );

  return useMemo(
    () => ({ isMarked, isPending, mark, unmark }),
    [isMarked, isPending, mark, unmark],
  );
}
