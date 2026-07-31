import { describe, expect, it } from 'vitest';

import { applyCompareInvalidation, isCompareStale } from '@/features/strategy-inputs/strategyInvalidationCoalescing';
import { applyStrategyInputChange, applyPreviewBecameStale, INITIAL_STRATEGY_INPUTS_STATE } from '@/features/strategy-inputs/strategyInputsState';

describe('compare invalidation via revision / stale', () => {
  it('clears when local revision invalidates a built compare', () => {
    const built = { result: { ok: true }, builtAtStrategyInputsRevision: 0 };
    const afterInput = applyStrategyInputChange(INITIAL_STRATEGY_INPUTS_STATE, 'profile_saved');
    expect(isCompareStale(built, afterInput.state.revision)).toBe(true);
    const cleared = applyCompareInvalidation(built, 'profile_saved');
    expect(cleared.didReset).toBe(true);
    expect(cleared.next.result).toBeNull();
  });

  it('clears on server stale without revision change', () => {
    const built = { result: { ok: true }, builtAtStrategyInputsRevision: 2 };
    const afterStale = applyPreviewBecameStale(
      { revision: 2, lastChange: null, invalidationSeq: 0 },
      'server_stale_memory',
    );
    expect(afterStale.state.revision).toBe(2);
    const cleared = applyCompareInvalidation(built, 'server_stale_memory');
    expect(cleared.didReset).toBe(true);
  });

  it('preserves compare for no-op reason', () => {
    const built = { result: { ok: true }, builtAtStrategyInputsRevision: 1 };
    const cleared = applyCompareInvalidation(built, 'behavior_snoozed');
    expect(cleared.didReset).toBe(false);
    expect(cleared.next.result).toEqual(built.result);
  });
});
