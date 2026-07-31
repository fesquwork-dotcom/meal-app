import { describe, expect, it } from 'vitest';

import { isPreviewStale } from '@/features/strategy-inputs/previewLifecycle';
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
      has_applied_signals: false,
      applied_count: 0,
      ignored_count: 0,
      types: [],
    },
    preview_token: 'signed.token.value',
    preview_expires_at: '2026-07-13T10:15:00+00:00',
    memory_unavailable: false,
  };
}

describe('preview lifecycle', () => {
  it('records built revision on ready preview', () => {
    const next = generationPreviewReducer(INITIAL_GENERATION_PREVIEW_STATE, {
      type: 'preview_success',
      preview: readyPreview(),
      strategyInputsRevision: 4,
    });
    expect(next.phase).toBe('ready');
    expect(next.previewBuiltAtRevision).toBe(4);
    expect(isPreviewStale(next, 4)).toBe(false);
  });

  it('is stale when revision diverges', () => {
    const ready = generationPreviewReducer(INITIAL_GENERATION_PREVIEW_STATE, {
      type: 'preview_success',
      preview: readyPreview(),
      strategyInputsRevision: 1,
    });
    expect(isPreviewStale(ready, 2)).toBe(true);
  });

  it('no preview is not stale', () => {
    expect(isPreviewStale(INITIAL_GENERATION_PREVIEW_STATE, 3)).toBe(false);
  });

  it('rebuild after stale uses current revision', () => {
    const stale = generationPreviewReducer(
      {
        ...INITIAL_GENERATION_PREVIEW_STATE,
        phase: 'ready',
        preview: readyPreview(),
        previewBuiltAtRevision: 1,
        planStartDate: '2026-07-13',
      },
      {
        type: 'strategy_inputs_changed',
        reason: 'profile_saved',
        messageKey: 'profile_changed',
      },
    );
    expect(stale.phase).toBe('stale');
    expect(stale.previewBuiltAtRevision).toBeNull();

    const rebuilt = generationPreviewReducer(stale, {
      type: 'preview_success',
      preview: readyPreview(),
      strategyInputsRevision: 2,
    });
    expect(rebuilt.previewBuiltAtRevision).toBe(2);
    expect(isPreviewStale(rebuilt, 2)).toBe(false);
  });
});
