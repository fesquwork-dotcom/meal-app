import type { StrategyInputChangeMessageKey } from '@/features/strategy-inputs/types';

/** Explicit preview lifecycle contract (Sprint 5.30). */
export type PreviewLifecycleStatus =
  | 'empty'
  | 'building'
  | 'ready'
  | 'generating'
  | 'stale'
  | 'expired'
  | 'error';

export interface PreviewLifecycleSnapshot {
  status: PreviewLifecycleStatus;
  previewBuiltAtRevision: number | null;
  hasPreviewToken: boolean;
  messageKey: StrategyInputChangeMessageKey | null;
}

export function isPreviewStale(
  state: {
    preview: { preview_token?: string | null } | null;
    previewBuiltAtRevision: number | null;
  },
  currentStrategyInputsRevision: number,
): boolean {
  if (!state.preview) {
    return false;
  }
  if (state.previewBuiltAtRevision == null) {
    return true;
  }
  return state.previewBuiltAtRevision !== currentStrategyInputsRevision;
}

export function hasUsablePreviewContent(state: {
  preview: unknown | null;
  activeConflict?: unknown | null;
  phase: string;
}): boolean {
  return (
    state.preview != null ||
    state.activeConflict != null ||
    state.phase === 'ready' ||
    state.phase === 'conflict' ||
    state.phase === 'generating'
  );
}

export function isPreviewAlreadyCleared(state: { phase: string; preview: unknown | null }): boolean {
  return (
    state.preview == null && (state.phase === 'stale' || state.phase === 'expired')
  );
}
