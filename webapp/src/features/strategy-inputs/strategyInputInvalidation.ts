import type {
  StrategyInputChangeMessageKey,
  StrategyInputChangeReason,
  StrategyInputInvalidationEffect,
  StrategyInvalidationEventKind,
} from '@/features/strategy-inputs/types';
import { isServerPreviewStaleReason } from '@/features/strategy-inputs/types';

const NOOP: StrategyInputInvalidationEffect = {
  invalidatePreview: false,
  invalidateCompare: false,
  invalidateCurrentMenu: false,
  messageKey: null,
  incrementsRevision: false,
  eventKind: 'input_changed',
};

function effect(
  messageKey: StrategyInputChangeMessageKey | null,
  options: {
    invalidate: boolean;
    incrementsRevision: boolean;
    eventKind: StrategyInvalidationEventKind;
  },
): StrategyInputInvalidationEffect {
  return {
    invalidatePreview: options.invalidate,
    invalidateCompare: options.invalidate,
    invalidateCurrentMenu: false,
    messageKey,
    incrementsRevision: options.incrementsRevision && options.invalidate,
    eventKind: options.eventKind,
  };
}

/** Pure invalidation matrix for strategy input / preview-stale reasons. */
export function getStrategyInputInvalidationEffect(
  reason: StrategyInputChangeReason,
): StrategyInputInvalidationEffect {
  if (isServerPreviewStaleReason(reason)) {
    switch (reason) {
      case 'server_stale_profile':
        return effect('server_profile_changed', {
          invalidate: true,
          incrementsRevision: false,
          eventKind: 'preview_stale',
        });
      case 'server_stale_memory':
        return effect('server_memory_changed', {
          invalidate: true,
          incrementsRevision: false,
          eventKind: 'preview_stale',
        });
      case 'server_stale_behavior':
        return effect('server_behavior_changed', {
          invalidate: true,
          incrementsRevision: false,
          eventKind: 'preview_stale',
        });
      case 'server_stale_learned_preferences':
        return effect('server_learned_preferences_changed', {
          invalidate: true,
          incrementsRevision: false,
          eventKind: 'preview_stale',
        });
      case 'server_stale_generic':
        return effect('settings_changed', {
          invalidate: true,
          incrementsRevision: false,
          eventKind: 'preview_stale',
        });
      case 'preview_token_expired':
        return effect('preview_expired', {
          invalidate: true,
          incrementsRevision: false,
          eventKind: 'preview_stale',
        });
      case 'preview_version_mismatch':
        return effect('application_updated', {
          invalidate: true,
          incrementsRevision: false,
          eventKind: 'preview_stale',
        });
      case 'preview_token_invalid':
        return effect('preview_invalid', {
          invalidate: true,
          incrementsRevision: false,
          eventKind: 'preview_stale',
        });
    }
  }

  switch (reason) {
    case 'profile_saved':
    case 'profile_rebased':
    case 'external_profile_update':
    case 'learning_recommendation_applied':
      return effect('profile_changed', {
        invalidate: true,
        incrementsRevision: true,
        eventKind: 'input_changed',
      });

    case 'memory_confirmed':
    case 'memory_dismissed':
    case 'memory_confirmed_dismissed':
    case 'memory_promoted':
      return effect('memory_changed', {
        invalidate: true,
        incrementsRevision: true,
        eventKind: 'input_changed',
      });

    case 'memory_candidate_dismissed':
      return { ...NOOP, eventKind: 'input_changed' };

    case 'behavior_confirmed':
    case 'behavior_revoked':
    case 'behavior_recommendation_applied':
      return effect('behavior_changed', {
        invalidate: true,
        incrementsRevision: true,
        eventKind: 'input_changed',
      });

    case 'learned_preference_accepted':
    case 'learned_preference_revoked':
      return effect('learned_preference_changed', {
        invalidate: true,
        incrementsRevision: true,
        eventKind: 'input_changed',
      });

    case 'behavior_snoozed':
    case 'behavior_candidate_dismissed':
      return { ...NOOP, eventKind: 'input_changed' };

    case 'conflict_resolved':
      return effect('conflict_resolved', {
        invalidate: true,
        incrementsRevision: true,
        eventKind: 'input_changed',
      });

    case 'plan_start_date_changed':
      return effect('plan_date_changed', {
        invalidate: true,
        incrementsRevision: true,
        eventKind: 'input_changed',
      });

    case 'unknown':
    default:
      return effect('settings_changed', {
        invalidate: true,
        incrementsRevision: true,
        eventKind: 'input_changed',
      });
  }
}
