import type { StrategyConflict, StrategyPreviewResponse } from '@/types/strategyPreview';
import { buildPreviewCookingPreferenceLine } from '@/features/strategy/appliedCookingSettingsViewModel';
import { buildPreviewPlanningPreferenceLine } from '@/features/strategy/appliedPlanningSettingsViewModel';
import { buildPreviewBehaviorLine } from '@/features/strategy/appliedBehaviorSettingsViewModel';
import { getStrategyInputChangeMessage } from '@/features/strategy-inputs/strategyInputMessages';
import { applyPreviewInvalidation } from '@/features/strategy-inputs/strategyInvalidationCoalescing';
import type {
  StrategyInputChangeMessageKey,
  StrategyInputChangeReason,
} from '@/features/strategy-inputs/types';

export type GenerationPreviewPhase =
  | 'idle'
  | 'saving'
  | 'previewing'
  | 'ready'
  | 'conflict'
  | 'generating'
  | 'stale'
  | 'expired';

export interface GenerationPreviewState {
  phase: GenerationPreviewPhase;
  preview: StrategyPreviewResponse | null;
  activeConflict: StrategyConflict | null;
  error: string | null;
  planStartDate: string | null;
  previewBuiltAtRevision: number | null;
  staleMessageKey: StrategyInputChangeMessageKey | null;
}

export type GenerationPreviewAction =
  | { type: 'reset' }
  | { type: 'save_start' }
  | { type: 'preview_start'; planStartDate: string }
  | {
      type: 'preview_success';
      preview: StrategyPreviewResponse;
      strategyInputsRevision: number;
    }
  | { type: 'preview_error'; error: string }
  | { type: 'show_conflict'; conflict: StrategyConflict }
  | { type: 'resolve_start' }
  | { type: 'generate_start' }
  | { type: 'generate_error'; error: string }
  | {
      type: 'strategy_inputs_changed';
      reason: StrategyInputChangeReason;
      messageKey: StrategyInputChangeMessageKey | null;
    }
  | { type: 'resolution_success' }
  | { type: 'requires_input'; field: string };

export const INITIAL_GENERATION_PREVIEW_STATE: GenerationPreviewState = {
  phase: 'idle',
  preview: null,
  activeConflict: null,
  error: null,
  planStartDate: null,
  previewBuiltAtRevision: null,
  staleMessageKey: null,
};

export function generationPreviewReducer(
  state: GenerationPreviewState,
  action: GenerationPreviewAction,
): GenerationPreviewState {
  switch (action.type) {
    case 'reset':
      return INITIAL_GENERATION_PREVIEW_STATE;
    case 'save_start':
      return {
        ...state,
        phase: 'saving',
        error: null,
      };
    case 'preview_start':
      return {
        ...state,
        phase: 'previewing',
        planStartDate: action.planStartDate,
        error: null,
        activeConflict: null,
        preview: null,
        previewBuiltAtRevision: null,
        staleMessageKey: null,
      };
    case 'preview_success': {
      const preview = action.preview;
      if (preview.status === 'conflict' && preview.conflicts.length > 0) {
        return {
          phase: 'conflict',
          preview,
          activeConflict: preview.conflicts[0],
          error: null,
          planStartDate: state.planStartDate,
          previewBuiltAtRevision: action.strategyInputsRevision,
          staleMessageKey: null,
        };
      }
      return {
        phase: 'ready',
        preview,
        activeConflict: null,
        error: null,
        planStartDate: state.planStartDate,
        previewBuiltAtRevision: action.strategyInputsRevision,
        staleMessageKey: null,
      };
    }
    case 'preview_error':
      return {
        ...state,
        phase: 'idle',
        error: action.error,
        previewBuiltAtRevision: null,
      };
    case 'show_conflict':
      return {
        ...state,
        phase: 'conflict',
        activeConflict: action.conflict,
      };
    case 'resolve_start':
      return {
        ...state,
        phase: 'previewing',
        error: null,
      };
    case 'generate_start':
      return {
        ...state,
        phase: 'generating',
        error: null,
      };
    case 'generate_error':
      return {
        ...state,
        phase: state.preview?.status === 'ready' ? 'ready' : 'idle',
        error: action.error,
      };
    case 'strategy_inputs_changed': {
      const applied = applyPreviewInvalidation(
        {
          phase: state.phase,
          preview: state.preview,
          activeConflict: state.activeConflict,
          planStartDate: state.planStartDate,
          previewBuiltAtRevision: state.previewBuiltAtRevision,
          staleMessageKey: state.staleMessageKey,
          error: state.error,
        },
        action.reason,
      );
      const next = applied.next;
      return {
        ...state,
        phase: next.phase as GenerationPreviewPhase,
        preview: next.preview as StrategyPreviewResponse | null,
        activeConflict: next.activeConflict as StrategyConflict | null,
        error:
          next.error ??
          getStrategyInputChangeMessage(action.messageKey) ??
          getStrategyInputChangeMessage('settings_changed'),
        planStartDate: next.planStartDate,
        previewBuiltAtRevision: next.previewBuiltAtRevision,
        staleMessageKey: next.staleMessageKey ?? action.messageKey,
      };
    }
    case 'resolution_success':
      return {
        ...INITIAL_GENERATION_PREVIEW_STATE,
        planStartDate: state.planStartDate,
      };
    case 'requires_input':
      return {
        ...INITIAL_GENERATION_PREVIEW_STATE,
        error:
          action.field === 'proteins'
            ? 'Выберите новый источник белка'
            : 'Требуется уточнение настроек',
      };
    default:
      return state;
  }
}

export function isPreviewTokenExpired(expiresAt: string | null | undefined): boolean {
  if (!expiresAt) {
    return false;
  }
  const expiresMs = Date.parse(expiresAt);
  if (Number.isNaN(expiresMs)) {
    return false;
  }
  return Date.now() >= expiresMs;
}

export function buildPreviewSummaryLines(preview: StrategyPreviewResponse): string[] {
  const lines: string[] = [];
  const strategy = preview.strategy;
  const explanation = preview.explanation;

  if (explanation?.headline) {
    lines.push(explanation.headline);
  } else if (strategy) {
    lines.push(`План на ${strategy.days} дней`);
  }

  if (strategy?.cook_days?.length) {
    lines.push(`Готовим в дни ${strategy.cook_days.join(', ')}`);
  }

  if (strategy?.cooking_time_limit) {
    lines.push(`До ${strategy.cooking_time_limit} минут активной готовки`);
  }

  const cookingLine = buildPreviewCookingPreferenceLine(preview.applied_settings?.cooking);
  if (cookingLine) {
    lines.push(cookingLine);
  }

  const planningLine = buildPreviewPlanningPreferenceLine(preview.applied_settings?.planning);
  if (planningLine) {
    lines.push(planningLine);
  }

  const behaviorLine = buildPreviewBehaviorLine(preview.applied_settings?.behavior);
  if (behaviorLine) {
    lines.push(behaviorLine);
  }

  if (preview.memory_summary?.has_applied_signals && !cookingLine) {
    lines.push('Учтены подтверждённые предпочтения');
  }

  if (preview.memory_unavailable) {
    lines.push('Сохранённые предпочтения временно недоступны');
  }

  const warning = preview.warnings.find((item) => item.severity === 'warning');
  if (warning) {
    lines.push(warning.description);
  }

  return lines.slice(0, 5);
}
