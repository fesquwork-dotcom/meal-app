import { describe, expect, it } from 'vitest';

import {
  applyPreviewBecameStale,
  applyStrategyInputChange,
  INITIAL_STRATEGY_INPUTS_STATE,
} from '@/features/strategy-inputs/strategyInputsState';
import { getStrategyInputInvalidationEffect } from '@/features/strategy-inputs/strategyInputInvalidation';

describe('Profile integration contract', () => {
  it('save maps to profile_saved and invalidates once', () => {
    const result = applyStrategyInputChange(INITIAL_STRATEGY_INPUTS_STATE, 'profile_saved');
    expect(result.state.revision).toBe(1);
    expect(result.effect.messageKey).toBe('profile_changed');
  });

  it('initial load is not an event', () => {
    expect(INITIAL_STRATEGY_INPUTS_STATE.revision).toBe(0);
    expect(INITIAL_STRATEGY_INPUTS_STATE.lastChange).toBeNull();
  });
});

describe('Memory / Behavior integration contract', () => {
  it('confirm invalidates; snooze does not', () => {
    expect(getStrategyInputInvalidationEffect('memory_confirmed').incrementsRevision).toBe(true);
    expect(getStrategyInputInvalidationEffect('behavior_snoozed').incrementsRevision).toBe(false);
  });
});

describe('Server stale contract', () => {
  it('does not bump strategy inputs revision', () => {
    const result = applyPreviewBecameStale(
      INITIAL_STRATEGY_INPUTS_STATE,
      'server_stale_behavior',
    );
    expect(result.state.revision).toBe(0);
    expect(result.effect.eventKind).toBe('preview_stale');
  });
});
