import { getStrategyInputInvalidationEffect } from '@/features/strategy-inputs/strategyInputInvalidation';
import {
  getStrategyInputChangeMessage,
  shouldReplaceStaleMessage,
} from '@/features/strategy-inputs/strategyInputMessages';
import {
  hasUsablePreviewContent,
  isPreviewAlreadyCleared,
} from '@/features/strategy-inputs/previewLifecycle';
import type {
  StrategyInputChangeMessageKey,
  StrategyInputChangeReason,
} from '@/features/strategy-inputs/types';

export interface PreviewInvalidationTarget {
  phase: string;
  preview: unknown | null;
  activeConflict: unknown | null;
  planStartDate: string | null;
  previewBuiltAtRevision: number | null;
  staleMessageKey: StrategyInputChangeMessageKey | null;
  error: string | null;
}

export interface PreviewInvalidationResult {
  next: PreviewInvalidationTarget;
  didReset: boolean;
  coalesced: boolean;
  messageUpdated: boolean;
}

/** Apply coordinator invalidation to preview state with duplicate-stale coalescing. */
export function applyPreviewInvalidation(
  state: PreviewInvalidationTarget,
  reason: StrategyInputChangeReason,
): PreviewInvalidationResult {
  const effect = getStrategyInputInvalidationEffect(reason);
  if (!effect.invalidatePreview) {
    return { next: state, didReset: false, coalesced: false, messageUpdated: false };
  }

  const nextMessageKey = effect.messageKey;
  const nextMessage = getStrategyInputChangeMessage(nextMessageKey);
  const cleared =
    isPreviewAlreadyCleared(state) ||
    ((state.phase === 'stale' || state.phase === 'expired') && state.preview == null);

  if (cleared && !hasUsablePreviewContent(state)) {
    const replace = shouldReplaceStaleMessage(state.staleMessageKey, nextMessageKey);
    if (!replace) {
      return { next: state, didReset: false, coalesced: true, messageUpdated: false };
    }
    return {
      next: {
        ...state,
        phase: reason === 'preview_token_expired' ? 'expired' : state.phase === 'expired' ? 'expired' : 'stale',
        staleMessageKey: nextMessageKey,
        error: nextMessage,
        preview: null,
        activeConflict: null,
        previewBuiltAtRevision: null,
      },
      didReset: false,
      coalesced: true,
      messageUpdated: true,
    };
  }

  if (!hasUsablePreviewContent(state)) {
    return { next: state, didReset: false, coalesced: true, messageUpdated: false };
  }

  return {
    next: {
      ...state,
      phase: reason === 'preview_token_expired' ? 'expired' : 'stale',
      preview: null,
      activeConflict: null,
      previewBuiltAtRevision: null,
      staleMessageKey: nextMessageKey,
      error: nextMessage,
      planStartDate: state.planStartDate,
    },
    didReset: true,
    coalesced: false,
    messageUpdated: true,
  };
}

export interface CompareInvalidationTarget {
  result: unknown | null;
  builtAtStrategyInputsRevision: number | null;
}

export interface CompareInvalidationResult {
  next: CompareInvalidationTarget;
  didReset: boolean;
  coalesced: boolean;
}

export function applyCompareInvalidation(
  state: CompareInvalidationTarget,
  reason: StrategyInputChangeReason,
): CompareInvalidationResult {
  const effect = getStrategyInputInvalidationEffect(reason);
  if (!effect.invalidateCompare) {
    return { next: state, didReset: false, coalesced: false };
  }

  if (state.result == null) {
    return { next: state, didReset: false, coalesced: true };
  }

  return {
    next: { result: null, builtAtStrategyInputsRevision: null },
    didReset: true,
    coalesced: false,
  };
}

export function isCompareStale(
  state: CompareInvalidationTarget,
  currentStrategyInputsRevision: number,
): boolean {
  if (state.result == null) {
    return false;
  }
  if (state.builtAtStrategyInputsRevision == null) {
    return true;
  }
  return state.builtAtStrategyInputsRevision !== currentStrategyInputsRevision;
}
