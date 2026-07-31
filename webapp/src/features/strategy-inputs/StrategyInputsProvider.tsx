import { useCallback, useMemo, useReducer, type ReactNode } from 'react';
import { StrategyInputsContext } from '@/features/strategy-inputs/StrategyInputsContext';
import { getStrategyInputInvalidationEffect } from '@/features/strategy-inputs/strategyInputInvalidation';
import {
  INITIAL_STRATEGY_INPUTS_STATE,
  strategyInputsReducer,
} from '@/features/strategy-inputs/strategyInputsState';
import type {
  LocalStrategyInputChangeReason,
  ServerPreviewStaleReason,
  StrategyInputChangeReason,
  StrategyInputInvalidationEffect,
} from '@/features/strategy-inputs/types';

function logInvalidation(
  eventName: string,
  reason: StrategyInputChangeReason,
  effect: StrategyInputInvalidationEffect,
  extras: Record<string, unknown> = {},
): void {
  if (import.meta.env.PROD) {
    return;
  }
  console.info(eventName, {
    reason,
    event_kind: effect.eventKind,
    preview_invalidated: effect.invalidatePreview,
    compare_invalidated: effect.invalidateCompare,
    revision_changed: effect.incrementsRevision,
    ...extras,
  });
}

export function StrategyInputsProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(strategyInputsReducer, INITIAL_STRATEGY_INPUTS_STATE);

  const notifyStrategyInputsChanged = useCallback(
    (reason: LocalStrategyInputChangeReason): StrategyInputInvalidationEffect => {
      const effect = getStrategyInputInvalidationEffect(reason);
      dispatch({ type: 'notify_input_changed', reason });
      if (!effect.invalidatePreview && !effect.invalidateCompare) {
        logInvalidation('strategy_input_change_noop', reason, effect);
      } else {
        logInvalidation('strategy_input_changed', reason, effect);
      }
      return effect;
    },
    [],
  );

  const notifyPreviewBecameStale = useCallback(
    (reason: ServerPreviewStaleReason): StrategyInputInvalidationEffect => {
      const effect = getStrategyInputInvalidationEffect(reason);
      dispatch({ type: 'notify_preview_stale', reason });
      logInvalidation('preview_became_stale', reason, effect);
      return effect;
    },
    [],
  );

  const value = useMemo(
    () => ({
      revision: state.revision,
      lastChange: state.lastChange,
      invalidationSeq: state.invalidationSeq,
      notifyStrategyInputsChanged,
      notifyPreviewBecameStale,
    }),
    [
      state.revision,
      state.lastChange,
      state.invalidationSeq,
      notifyStrategyInputsChanged,
      notifyPreviewBecameStale,
    ],
  );

  return (
    <StrategyInputsContext.Provider value={value}>{children}</StrategyInputsContext.Provider>
  );
}
