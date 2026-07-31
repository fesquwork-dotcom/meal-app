/** Typed strategy-input and preview-stale contracts (Sprint 5.29–5.30). */

export type StrategyInvalidationEventKind = 'input_changed' | 'preview_stale';

/** Local mutations of future strategy inputs. */
export type LocalStrategyInputChangeReason =
  | 'profile_saved'
  | 'profile_rebased'
  | 'memory_confirmed'
  | 'memory_dismissed'
  | 'memory_candidate_dismissed'
  | 'memory_confirmed_dismissed'
  | 'memory_promoted'
  | 'behavior_confirmed'
  | 'behavior_revoked'
  | 'behavior_snoozed'
  | 'behavior_candidate_dismissed'
  | 'behavior_recommendation_applied'
  | 'learning_recommendation_applied'
  | 'learned_preference_accepted'
  | 'learned_preference_revoked'
  | 'conflict_resolved'
  | 'plan_start_date_changed'
  | 'external_profile_update'
  | 'unknown';

/**
 * Server/token detection that a built preview is unusable.
 * Does not bump strategy-inputs revision.
 */
export type ServerPreviewStaleReason =
  | 'server_stale_profile'
  | 'server_stale_memory'
  | 'server_stale_behavior'
  | 'server_stale_learned_preferences'
  | 'server_stale_generic'
  | 'preview_token_expired'
  | 'preview_version_mismatch'
  | 'preview_token_invalid';

export type StrategyInputChangeReason =
  | LocalStrategyInputChangeReason
  | ServerPreviewStaleReason;

export type StrategyInputChangeMessageKey =
  | 'profile_changed'
  | 'memory_changed'
  | 'behavior_changed'
  | 'learned_preference_changed'
  | 'conflict_resolved'
  | 'plan_date_changed'
  | 'settings_changed'
  | 'server_profile_changed'
  | 'server_memory_changed'
  | 'server_behavior_changed'
  | 'server_learned_preferences_changed'
  | 'preview_expired'
  | 'application_updated'
  | 'preview_invalid';

export type StrategyInputChangeSource =
  | 'profile'
  | 'memory'
  | 'behavior'
  | 'learned_preference'
  | 'conflict'
  | 'calendar'
  | 'server'
  | 'token';

export interface StrategyInputChangeEvent {
  reason: StrategyInputChangeReason;
  kind: StrategyInvalidationEventKind;
  occurredAt: number;
  source?: StrategyInputChangeSource;
}

export interface StrategyInputInvalidationEffect {
  invalidatePreview: boolean;
  invalidateCompare: boolean;
  /** Future strategy inputs never clear the current MenuPlan. */
  invalidateCurrentMenu: false;
  messageKey: StrategyInputChangeMessageKey | null;
  incrementsRevision: boolean;
  eventKind: StrategyInvalidationEventKind;
}

export const SERVER_PREVIEW_STALE_REASONS: readonly ServerPreviewStaleReason[] = [
  'server_stale_profile',
  'server_stale_memory',
  'server_stale_behavior',
  'server_stale_learned_preferences',
  'server_stale_generic',
  'preview_token_expired',
  'preview_version_mismatch',
  'preview_token_invalid',
] as const;

export function isServerPreviewStaleReason(
  reason: StrategyInputChangeReason,
): reason is ServerPreviewStaleReason {
  return (SERVER_PREVIEW_STALE_REASONS as readonly string[]).includes(reason);
}

export function isLocalStrategyInputChangeReason(
  reason: StrategyInputChangeReason,
): reason is LocalStrategyInputChangeReason {
  return !isServerPreviewStaleReason(reason);
}
