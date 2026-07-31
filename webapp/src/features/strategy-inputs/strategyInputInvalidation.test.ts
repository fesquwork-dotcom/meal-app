import { describe, expect, it } from 'vitest';

import { getStrategyInputInvalidationEffect } from '@/features/strategy-inputs/strategyInputInvalidation';
import type { StrategyInputChangeReason } from '@/features/strategy-inputs/types';

const ALL_REASONS: StrategyInputChangeReason[] = [
  'profile_saved',
  'profile_rebased',
  'memory_confirmed',
  'memory_dismissed',
  'memory_candidate_dismissed',
  'memory_confirmed_dismissed',
  'memory_promoted',
  'behavior_confirmed',
  'behavior_revoked',
  'behavior_snoozed',
  'behavior_candidate_dismissed',
  'learned_preference_accepted',
  'learned_preference_revoked',
  'behavior_recommendation_applied',
  'conflict_resolved',
  'plan_start_date_changed',
  'external_profile_update',
  'unknown',
  'server_stale_profile',
  'server_stale_memory',
  'server_stale_behavior',
  'server_stale_learned_preferences',
  'server_stale_generic',
  'preview_token_expired',
  'preview_version_mismatch',
  'preview_token_invalid',
];

describe('getStrategyInputInvalidationEffect', () => {
  it.each([
    ['profile_saved', true, true, true, 'profile_changed', 'input_changed'],
    ['behavior_snoozed', false, false, false, null, 'input_changed'],
    ['memory_candidate_dismissed', false, false, false, null, 'input_changed'],
    ['server_stale_profile', true, true, false, 'server_profile_changed', 'preview_stale'],
    ['server_stale_memory', true, true, false, 'server_memory_changed', 'preview_stale'],
    ['server_stale_behavior', true, true, false, 'server_behavior_changed', 'preview_stale'],
    [
      'server_stale_learned_preferences',
      true,
      true,
      false,
      'server_learned_preferences_changed',
      'preview_stale',
    ],
    [
      'learned_preference_accepted',
      true,
      true,
      true,
      'learned_preference_changed',
      'input_changed',
    ],
    [
      'learned_preference_revoked',
      true,
      true,
      true,
      'learned_preference_changed',
      'input_changed',
    ],
    ['preview_token_expired', true, true, false, 'preview_expired', 'preview_stale'],
    ['preview_version_mismatch', true, true, false, 'application_updated', 'preview_stale'],
    ['preview_token_invalid', true, true, false, 'preview_invalid', 'preview_stale'],
    ['unknown', true, true, true, 'settings_changed', 'input_changed'],
  ] as const)(
    '%s',
    (reason, invalidatePreview, invalidateCompare, incrementsRevision, messageKey, eventKind) => {
      const effect = getStrategyInputInvalidationEffect(reason);
      expect(effect.invalidatePreview).toBe(invalidatePreview);
      expect(effect.invalidateCompare).toBe(invalidateCompare);
      expect(effect.incrementsRevision).toBe(incrementsRevision);
      expect(effect.invalidateCurrentMenu).toBe(false);
      expect(effect.messageKey).toBe(messageKey);
      expect(effect.eventKind).toBe(eventKind);
    },
  );

  it('never clears MenuPlan for any reason', () => {
    for (const reason of ALL_REASONS) {
      expect(getStrategyInputInvalidationEffect(reason).invalidateCurrentMenu).toBe(false);
    }
  });
});
