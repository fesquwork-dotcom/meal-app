import { describe, expect, it } from 'vitest';

import {
  generationPreviewReducer,
  INITIAL_GENERATION_PREVIEW_STATE,
} from '@/features/menu-generator/generationPreviewReducer';
import type { StrategyPreviewResponse } from '@/types/strategyPreview';

function readyPreview(): StrategyPreviewResponse {
  return {
    status: 'ready',
    preview_version: 1,
    strategy: {
      days: 7,
      cooking_time_limit: 20,
      cook_days: [1, 3, 5, 7],
      excluded_products: [],
      preferred_proteins: ['any'],
    },
    explanation: {
      version: 1,
      source: 'recorded',
      headline: 'План на 7 дней',
      summary: 'Краткое описание',
      reasons: [],
    },
    conflicts: [],
    warnings: [],
    memory_summary: {
      has_applied_signals: true,
      applied_count: 1,
      ignored_count: 0,
      types: ['prefer_faster_meals'],
    },
    preview_token: 'signed.token.value',
    preview_expires_at: '2026-07-13T10:15:00+00:00',
    memory_unavailable: false,
  };
}

describe('generationPreviewReducer strategy_inputs_changed', () => {
  const readyState = {
    ...INITIAL_GENERATION_PREVIEW_STATE,
    phase: 'ready' as const,
    preview: readyPreview(),
    planStartDate: '2026-07-13',
    previewBuiltAtRevision: 0,
  };

  it('clears preview token and conflict data with stale message', () => {
    const next = generationPreviewReducer(readyState, {
      type: 'strategy_inputs_changed',
      reason: 'profile_saved',
      messageKey: 'profile_changed',
    });
    expect(next.phase).toBe('stale');
    expect(next.preview).toBeNull();
    expect(next.activeConflict).toBeNull();
    expect(next.error).toContain('профиля');
    expect(next.planStartDate).toBe('2026-07-13');
  });

  it('uses server copy for server_stale_profile', () => {
    const next = generationPreviewReducer(readyState, {
      type: 'strategy_inputs_changed',
      reason: 'server_stale_profile',
      messageKey: 'server_profile_changed',
    });
    expect(next.error).toContain('другой сессии');
  });

  it('uses expired phase for preview_token_expired', () => {
    const next = generationPreviewReducer(readyState, {
      type: 'strategy_inputs_changed',
      reason: 'preview_token_expired',
      messageKey: 'preview_expired',
    });
    expect(next.phase).toBe('expired');
    expect(next.error).toContain('истекло');
  });

  it('coalesces duplicate stale without wiping planStartDate', () => {
    const first = generationPreviewReducer(readyState, {
      type: 'strategy_inputs_changed',
      reason: 'profile_saved',
      messageKey: 'profile_changed',
    });
    const second = generationPreviewReducer(first, {
      type: 'strategy_inputs_changed',
      reason: 'server_stale_profile',
      messageKey: 'server_profile_changed',
    });
    expect(second.planStartDate).toBe('2026-07-13');
    expect(second.error).toContain('другой сессии');
  });
});
