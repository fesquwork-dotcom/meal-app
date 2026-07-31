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

describe('generationPreviewReducer', () => {
  it('moves to ready on successful preview', () => {
    const next = generationPreviewReducer(INITIAL_GENERATION_PREVIEW_STATE, {
      type: 'preview_success',
      preview: readyPreview(),
      strategyInputsRevision: 0,
    });
    expect(next.phase).toBe('ready');
    expect(next.preview?.preview_token).toBe('signed.token.value');
    expect(next.previewBuiltAtRevision).toBe(0);
  });

  it('moves to conflict when preview has blocking conflicts', () => {
    const next = generationPreviewReducer(INITIAL_GENERATION_PREVIEW_STATE, {
      type: 'preview_success',
      preview: {
        ...readyPreview(),
        status: 'conflict',
        strategy: null,
        conflicts: [
          {
            conflict_id: 'cfl_abc123def456',
            code: 'PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY',
            title: 'Нужно уточнить предпочтение',
            description: 'Рыба одновременно выбрана...',
            severity: 'blocking',
            field: 'proteins',
            options: [],
          },
        ],
      },
      strategyInputsRevision: 1,
    });
    expect(next.phase).toBe('conflict');
    expect(next.previewBuiltAtRevision).toBe(1);
  });

  it('clears preview token after resolution success', () => {
    const next = generationPreviewReducer(
      {
        ...INITIAL_GENERATION_PREVIEW_STATE,
        phase: 'conflict',
        preview: readyPreview(),
        planStartDate: '2026-07-13',
        previewBuiltAtRevision: 1,
      },
      { type: 'resolution_success' },
    );
    expect(next.preview).toBeNull();
    expect(next.planStartDate).toBe('2026-07-13');
  });

  it('strategy_inputs_changed clears token without touching generation MenuPlan state', () => {
    const next = generationPreviewReducer(
      {
        ...INITIAL_GENERATION_PREVIEW_STATE,
        phase: 'ready',
        preview: readyPreview(),
        planStartDate: '2026-07-13',
        previewBuiltAtRevision: 0,
      },
      {
        type: 'strategy_inputs_changed',
        reason: 'memory_confirmed',
        messageKey: 'memory_changed',
      },
    );
    expect(next.preview).toBeNull();
    expect(next.phase).toBe('stale');
    expect(next.planStartDate).toBe('2026-07-13');
    expect(next.error).toContain('предпочтения');
    expect(next.previewBuiltAtRevision).toBeNull();
  });

  it('handles requires_input for proteins', () => {
    const next = generationPreviewReducer(INITIAL_GENERATION_PREVIEW_STATE, {
      type: 'requires_input',
      field: 'proteins',
    });
    expect(next.error).toContain('белка');
  });
});

describe('buildPreviewSummaryLines', () => {
  it('includes memory and cook days without internal codes', async () => {
    const { buildPreviewSummaryLines } = await import(
      '@/features/menu-generator/generationPreviewReducer'
    );
    const lines = buildPreviewSummaryLines(readyPreview());
    expect(lines.some((line) => line.includes('Готовим'))).toBe(true);
    expect(lines.some((line) => line.includes('предпочт'))).toBe(true);
    expect(lines.join(' ')).not.toContain('MEMORY_');
  });
});
