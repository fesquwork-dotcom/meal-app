import { getStrategyInputInvalidationEffect } from '@/features/strategy-inputs/strategyInputInvalidation';
import type {
  LocalStrategyInputChangeReason,
  ServerPreviewStaleReason,
  StrategyInputChangeEvent,
  StrategyInputChangeReason,
  StrategyInputChangeSource,
  StrategyInputInvalidationEffect,
  StrategyInvalidationEventKind,
} from '@/features/strategy-inputs/types';
import { isServerPreviewStaleReason } from '@/features/strategy-inputs/types';

export interface StrategyInputsState {
  revision: number;
  lastChange: StrategyInputChangeEvent | null;
  /** Bumps when subscribers should re-evaluate preview/compare (input or stale). */
  invalidationSeq: number;
}

export const INITIAL_STRATEGY_INPUTS_STATE: StrategyInputsState = {
  revision: 0,
  lastChange: null,
  invalidationSeq: 0,
};

export type StrategyInputsAction =
  | {
      type: 'notify_input_changed';
      reason: LocalStrategyInputChangeReason;
      source?: StrategyInputChangeSource;
      occurredAt?: number;
    }
  | {
      type: 'notify_preview_stale';
      reason: ServerPreviewStaleReason;
      source?: StrategyInputChangeSource;
      occurredAt?: number;
    };

export interface StrategyInputsNotifyResult {
  state: StrategyInputsState;
  effect: StrategyInputInvalidationEffect;
}

function inferSource(reason: StrategyInputChangeReason): StrategyInputChangeSource | undefined {
  if (isServerPreviewStaleReason(reason)) {
    if (reason.startsWith('preview_')) {
      return 'token';
    }
    return 'server';
  }
  if (reason.startsWith('profile_') || reason === 'external_profile_update') {
    return 'profile';
  }
  if (reason.startsWith('memory_')) {
    return 'memory';
  }
  if (reason.startsWith('behavior_')) {
    return 'behavior';
  }
  if (reason.startsWith('learned_preference_')) {
    return 'learned_preference';
  }
  if (reason === 'conflict_resolved') {
    return 'conflict';
  }
  if (reason === 'plan_start_date_changed') {
    return 'calendar';
  }
  return undefined;
}

function applyNotify(
  state: StrategyInputsState,
  reason: StrategyInputChangeReason,
  kind: StrategyInvalidationEventKind,
  options: { source?: StrategyInputChangeSource; occurredAt?: number } = {},
): StrategyInputsNotifyResult {
  const effect = getStrategyInputInvalidationEffect(reason);
  const event: StrategyInputChangeEvent = {
    reason,
    kind,
    occurredAt: options.occurredAt ?? Date.now(),
    source: options.source ?? inferSource(reason),
  };

  const shouldSignalSubscribers = effect.invalidatePreview || effect.invalidateCompare;

  let revision = state.revision;
  if (effect.incrementsRevision) {
    revision = state.revision + 1;
  }

  const invalidationSeq = shouldSignalSubscribers
    ? state.invalidationSeq + 1
    : state.invalidationSeq;

  return {
    state: {
      revision,
      lastChange: event,
      invalidationSeq,
    },
    effect,
  };
}

/** Local input mutation — may bump strategy-inputs revision. */
export function applyStrategyInputChange(
  state: StrategyInputsState,
  reason: LocalStrategyInputChangeReason,
  options: { source?: StrategyInputChangeSource; occurredAt?: number } = {},
): StrategyInputsNotifyResult {
  return applyNotify(state, reason, 'input_changed', options);
}

/** Server/token stale detection — does not bump strategy-inputs revision. */
export function applyPreviewBecameStale(
  state: StrategyInputsState,
  reason: ServerPreviewStaleReason,
  options: { source?: StrategyInputChangeSource; occurredAt?: number } = {},
): StrategyInputsNotifyResult {
  return applyNotify(state, reason, 'preview_stale', options);
}

export function strategyInputsReducer(
  state: StrategyInputsState,
  action: StrategyInputsAction,
): StrategyInputsState {
  if (action.type === 'notify_input_changed') {
    return applyStrategyInputChange(state, action.reason, {
      source: action.source,
      occurredAt: action.occurredAt,
    }).state;
  }
  return applyPreviewBecameStale(state, action.reason, {
    source: action.source,
    occurredAt: action.occurredAt,
  }).state;
}
