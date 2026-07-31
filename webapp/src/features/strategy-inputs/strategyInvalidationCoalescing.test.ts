import { describe, expect, it } from 'vitest';

import {
  applyPreviewBecameStale,
  applyStrategyInputChange,
  INITIAL_STRATEGY_INPUTS_STATE,
} from '@/features/strategy-inputs/strategyInputsState';
import { applyPreviewInvalidation } from '@/features/strategy-inputs/strategyInvalidationCoalescing';
import { shouldReplaceStaleMessage } from '@/features/strategy-inputs/strategyInputMessages';

describe('strategy invalidation coalescing', () => {
  it('local invalidation + server stale does not bump revision twice', () => {
    let state = INITIAL_STRATEGY_INPUTS_STATE;
    state = applyStrategyInputChange(state, 'profile_saved').state;
    expect(state.revision).toBe(1);
    const seqAfterLocal = state.invalidationSeq;

    state = applyPreviewBecameStale(state, 'server_stale_profile').state;
    expect(state.revision).toBe(1);
    expect(state.invalidationSeq).toBe(seqAfterLocal + 1);
    expect(state.lastChange?.kind).toBe('preview_stale');
  });

  it('repeated server stale coalesces resets on already-cleared preview', () => {
    const ready = {
      phase: 'ready',
      preview: { preview_token: 'x' },
      activeConflict: null,
      planStartDate: '2026-07-13',
      previewBuiltAtRevision: 0,
      staleMessageKey: null,
      error: null,
    };
    const first = applyPreviewInvalidation(ready, 'profile_saved');
    expect(first.didReset).toBe(true);
    expect(first.next.phase).toBe('stale');

    const second = applyPreviewInvalidation(first.next, 'server_stale_profile');
    expect(second.didReset).toBe(false);
    expect(second.coalesced).toBe(true);
    expect(second.messageUpdated).toBe(true);
    expect(second.next.error).toContain('другой сессии');
  });

  it('server stale with no preview does not invent a user warning surface', () => {
    const idle = {
      phase: 'idle',
      preview: null,
      activeConflict: null,
      planStartDate: null,
      previewBuiltAtRevision: null,
      staleMessageKey: null,
      error: null,
    };
    const result = applyPreviewInvalidation(idle, 'server_stale_behavior');
    expect(result.didReset).toBe(false);
    expect(result.coalesced).toBe(true);
    expect(result.next.phase).toBe('idle');
  });

  it('higher-priority message replaces lower without reset', () => {
    expect(shouldReplaceStaleMessage('profile_changed', 'application_updated')).toBe(true);
    expect(shouldReplaceStaleMessage('application_updated', 'preview_expired')).toBe(false);
  });

  it('no revision bump for server stale', () => {
    const result = applyPreviewBecameStale(INITIAL_STRATEGY_INPUTS_STATE, 'preview_token_expired');
    expect(result.effect.incrementsRevision).toBe(false);
    expect(result.state.revision).toBe(0);
    expect(result.state.invalidationSeq).toBe(1);
  });
});
