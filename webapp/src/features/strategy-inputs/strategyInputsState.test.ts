import { describe, expect, it } from 'vitest';

import {
  applyPreviewBecameStale,
  applyStrategyInputChange,
  INITIAL_STRATEGY_INPUTS_STATE,
  strategyInputsReducer,
} from '@/features/strategy-inputs/strategyInputsState';
import { getStrategyInputChangeMessage } from '@/features/strategy-inputs/strategyInputMessages';
import { getStrategyInputInvalidationEffect } from '@/features/strategy-inputs/strategyInputInvalidation';
import type { StrategyInputChangeReason } from '@/features/strategy-inputs/types';

describe('applyStrategyInputChange', () => {
  it('increments revision for invalidating local reasons', () => {
    const first = applyStrategyInputChange(INITIAL_STRATEGY_INPUTS_STATE, 'profile_saved');
    expect(first.state.revision).toBe(1);
    expect(first.state.invalidationSeq).toBe(1);
    expect(first.state.lastChange?.kind).toBe('input_changed');

    const second = applyStrategyInputChange(first.state, 'behavior_revoked');
    expect(second.state.revision).toBe(2);
  });

  it('does not increment revision for no-op reasons', () => {
    const afterSnooze = applyStrategyInputChange(INITIAL_STRATEGY_INPUTS_STATE, 'behavior_snoozed');
    expect(afterSnooze.state.revision).toBe(0);
    expect(afterSnooze.state.invalidationSeq).toBe(0);
    expect(afterSnooze.state.lastChange?.reason).toBe('behavior_snoozed');
  });

  it('maps message keys via invalidation effect', () => {
    expect(
      applyStrategyInputChange(INITIAL_STRATEGY_INPUTS_STATE, 'conflict_resolved').effect
        .messageKey,
    ).toBe('conflict_resolved');
  });
});

describe('applyPreviewBecameStale', () => {
  it('signals subscribers without bumping revision', () => {
    const result = applyPreviewBecameStale(
      { revision: 2, lastChange: null, invalidationSeq: 2 },
      'server_stale_memory',
    );
    expect(result.state.revision).toBe(2);
    expect(result.state.invalidationSeq).toBe(3);
    expect(result.state.lastChange?.kind).toBe('preview_stale');
    expect(result.effect.incrementsRevision).toBe(false);
  });
});

describe('strategyInputsReducer', () => {
  it('handles input and stale notifies', () => {
    const afterInput = strategyInputsReducer(INITIAL_STRATEGY_INPUTS_STATE, {
      type: 'notify_input_changed',
      reason: 'behavior_confirmed',
    });
    expect(afterInput.revision).toBe(1);
    const afterStale = strategyInputsReducer(afterInput, {
      type: 'notify_preview_stale',
      reason: 'preview_version_mismatch',
    });
    expect(afterStale.revision).toBe(1);
    expect(afterStale.lastChange?.reason).toBe('preview_version_mismatch');
  });
});

describe('getStrategyInputChangeMessage', () => {
  it('returns localized stale copy for each key', () => {
    expect(getStrategyInputChangeMessage('profile_changed')).toContain('профиля');
    expect(getStrategyInputChangeMessage('server_profile_changed')).toContain('другой сессии');
    expect(getStrategyInputChangeMessage('preview_expired')).toContain('истекло');
    expect(getStrategyInputChangeMessage('application_updated')).toContain('обновилось');
    expect(getStrategyInputChangeMessage('preview_invalid')).toContain('нельзя использовать');
  });
});

describe('MenuPlan isolation', () => {
  const reasons: StrategyInputChangeReason[] = [
    'profile_saved',
    'server_stale_behavior',
    'preview_token_expired',
    'preview_version_mismatch',
  ];

  it('typed effect forever forbids MenuPlan clear', () => {
    for (const reason of reasons) {
      expect(getStrategyInputInvalidationEffect(reason).invalidateCurrentMenu).toBe(false);
    }
  });
});
