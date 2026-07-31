import {
  applyPreviewBecameStale,
  applyStrategyInputChange,
  INITIAL_STRATEGY_INPUTS_STATE,
  type StrategyInputsState,
} from '@/features/strategy-inputs/strategyInputsState';
import {
  applyCompareInvalidation,
  applyPreviewInvalidation,
  type CompareInvalidationTarget,
  type PreviewInvalidationTarget,
} from '@/features/strategy-inputs/strategyInvalidationCoalescing';
import type {
  LocalStrategyInputChangeReason,
  ServerPreviewStaleReason,
} from '@/features/strategy-inputs/types';
import type { MenuPlan } from '@/types/menu';

export interface ProfileDraftSnapshot {
  dirty: boolean;
  proteinCount: number;
  serverRevision: number;
}

export interface InvalidationHarness {
  inputs: StrategyInputsState;
  preview: PreviewInvalidationTarget;
  compare: CompareInvalidationTarget;
  menuPlan: MenuPlan;
  draft: ProfileDraftSnapshot;
  notifyInput(reason: LocalStrategyInputChangeReason): void;
  notifyStale(reason: ServerPreviewStaleReason): void;
  setReadyPreview(atRevision?: number): void;
  setCompareResult(atRevision?: number): void;
}

function cloneMenu(plan: MenuPlan): MenuPlan {
  return structuredClone(plan);
}

export function assertCurrentMenuUnchanged(before: MenuPlan, after: MenuPlan): void {
  if (before.strategy_id !== after.strategy_id) {
    throw new Error('strategy_id changed');
  }
  if (before.plan_start_date !== after.plan_start_date) {
    throw new Error('plan_start_date changed');
  }
  if (JSON.stringify(before.days_plan) !== JSON.stringify(after.days_plan)) {
    throw new Error('days_plan changed');
  }
  if (JSON.stringify(before.recipes) !== JSON.stringify(after.recipes)) {
    throw new Error('recipes changed');
  }
  if (JSON.stringify(before) !== JSON.stringify(after)) {
    throw new Error('menu plan envelope changed');
  }
}

export function createInvalidationHarness(menuPlan: MenuPlan): InvalidationHarness {
  let inputs = { ...INITIAL_STRATEGY_INPUTS_STATE };
  let preview: PreviewInvalidationTarget = {
    phase: 'idle',
    preview: null,
    activeConflict: null,
    planStartDate: null,
    previewBuiltAtRevision: null,
    staleMessageKey: null,
    error: null,
  };
  let compare: CompareInvalidationTarget = {
    result: null,
    builtAtStrategyInputsRevision: null,
  };
  const menu = cloneMenu(menuPlan);
  const draft: ProfileDraftSnapshot = {
    dirty: true,
    proteinCount: 2,
    serverRevision: 7,
  };

  function applyEffect(reason: LocalStrategyInputChangeReason | ServerPreviewStaleReason) {
    const menuBefore = cloneMenu(menu);
    const draftBefore = { ...draft };

    const previewApplied = applyPreviewInvalidation(preview, reason);
    preview = previewApplied.next;

    const compareApplied = applyCompareInvalidation(compare, reason);
    compare = compareApplied.next;

    assertCurrentMenuUnchanged(menuBefore, menu);
    if (
      draft.dirty !== draftBefore.dirty ||
      draft.proteinCount !== draftBefore.proteinCount ||
      draft.serverRevision !== draftBefore.serverRevision
    ) {
      throw new Error('profile draft changed by invalidation');
    }
  }

  return {
    get inputs() {
      return inputs;
    },
    get preview() {
      return preview;
    },
    get compare() {
      return compare;
    },
    get menuPlan() {
      return menu;
    },
    get draft() {
      return draft;
    },
    notifyInput(reason) {
      const result = applyStrategyInputChange(inputs, reason);
      inputs = result.state;
      applyEffect(reason);
    },
    notifyStale(reason) {
      const result = applyPreviewBecameStale(inputs, reason);
      inputs = result.state;
      applyEffect(reason);
    },
    setReadyPreview(atRevision) {
      preview = {
        phase: 'ready',
        preview: { preview_token: 'tok' },
        activeConflict: null,
        planStartDate: '2026-07-13',
        previewBuiltAtRevision: atRevision ?? inputs.revision,
        staleMessageKey: null,
        error: null,
      };
    },
    setCompareResult(atRevision) {
      compare = {
        result: { preview_token: 'cmp' },
        builtAtStrategyInputsRevision: atRevision ?? inputs.revision,
      };
    },
  };
}
