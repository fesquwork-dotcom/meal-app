import type { AsyncResourceState } from '@/features/async-resource/types';
import { createInitialAsyncResourceState } from '@/features/async-resource/types';
import {
  asyncResourceReducer,
  type AsyncResourceAction,
} from '@/features/async-resource/asyncResourceState';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';
import type { BehaviorInsight, BehaviorInsightsListResponse } from '@/types/behavior';

export type BehaviorActionType =
  | 'confirm'
  | 'dismiss'
  | 'snooze'
  | 'revoke'
  | 'apply_recommendation';

export interface BehaviorInsightsListData {
  insights: BehaviorInsight[];
  candidateCount: number;
  confirmedCount: number;
}

export interface BehaviorInsightsState {
  resource: AsyncResourceState<BehaviorInsightsListData>;
  actionInsightId: string | null;
  actionType: BehaviorActionType | null;
  /** @deprecated Prefer actionErrorsByInsightId — singular error for backward compat. */
  actionError: StrategyWorkflowError | null;
  actionErrorsByInsightId: Record<string, StrategyWorkflowError>;
}

export const initialBehaviorInsightsState: BehaviorInsightsState = {
  resource: createInitialAsyncResourceState(),
  actionInsightId: null,
  actionType: null,
  actionError: null,
  actionErrorsByInsightId: {},
};

export type BehaviorInsightsStateAction =
  | { type: 'resource'; action: AsyncResourceAction<BehaviorInsightsListData> }
  | { type: 'action_start'; insightId: string; actionType: BehaviorActionType }
  | { type: 'action_success_confirm'; insight: BehaviorInsight }
  | { type: 'action_success_apply_recommendation'; insight: BehaviorInsight }
  | { type: 'action_success_dismiss'; insightId: string }
  | { type: 'action_success_snooze'; insightId: string }
  | { type: 'action_success_revoke'; insightId: string }
  | { type: 'action_error'; error: StrategyWorkflowError; insightId?: string }
  | { type: 'clear_action_error'; insightId?: string };

export function mapListResponse(payload: BehaviorInsightsListResponse): BehaviorInsightsListData {
  return {
    insights: payload.insights,
    candidateCount: payload.candidate_count,
    confirmedCount: payload.confirmed_count,
  };
}

function withList(
  state: BehaviorInsightsState,
  update: (data: BehaviorInsightsListData) => BehaviorInsightsListData,
  clearedInsightId?: string,
): BehaviorInsightsState {
  const current = state.resource.data;
  if (!current) {
    return state;
  }
  const nextData = update(current);
  const nextIds = new Set(nextData.insights.map((item) => item.id));
  const nextErrors: Record<string, StrategyWorkflowError> = {};
  for (const [id, err] of Object.entries(state.actionErrorsByInsightId)) {
    if (nextIds.has(id) && id !== clearedInsightId) {
      nextErrors[id] = err;
    }
  }
  return {
    ...state,
    resource: {
      status: 'ready',
      data: nextData,
      error: null,
      lastUpdatedAt: Date.now(),
      requestId: state.resource.requestId,
    },
    actionInsightId: null,
    actionType: null,
    actionError: null,
    actionErrorsByInsightId: nextErrors,
  };
}

export function behaviorInsightsReducer(
  state: BehaviorInsightsState,
  action: BehaviorInsightsStateAction,
): BehaviorInsightsState {
  switch (action.type) {
    case 'resource':
      return {
        ...state,
        resource: asyncResourceReducer(state.resource, action.action),
      };
    case 'action_start': {
      const nextErrors = { ...state.actionErrorsByInsightId };
      delete nextErrors[action.insightId];
      return {
        ...state,
        actionInsightId: action.insightId,
        actionType: action.actionType,
        actionError: null,
        actionErrorsByInsightId: nextErrors,
      };
    }
    case 'action_success_confirm': {
      return withList(
        state,
        (data) => {
          const wasCandidate = data.insights.some(
            (item) => item.id === action.insight.id && item.status === 'candidate',
          );
          return {
            insights: data.insights.map((item) =>
              item.id === action.insight.id ? action.insight : item,
            ),
            candidateCount: wasCandidate
              ? Math.max(0, data.candidateCount - 1)
              : data.candidateCount,
            confirmedCount: data.confirmedCount + (wasCandidate ? 1 : 0),
          };
        },
        action.insight.id,
      );
    }
    case 'action_success_apply_recommendation': {
      return withList(
        state,
        (data) => ({
          ...data,
          insights: data.insights.map((item) =>
            item.id === action.insight.id ? action.insight : item,
          ),
        }),
        action.insight.id,
      );
    }
    case 'action_success_dismiss':
    case 'action_success_snooze': {
      return withList(
        state,
        (data) => {
          const removed = data.insights.find((item) => item.id === action.insightId);
          return {
            insights: data.insights.filter((item) => item.id !== action.insightId),
            candidateCount:
              removed?.status === 'candidate'
                ? Math.max(0, data.candidateCount - 1)
                : data.candidateCount,
            confirmedCount:
              removed?.status === 'confirmed'
                ? Math.max(0, data.confirmedCount - 1)
                : data.confirmedCount,
          };
        },
        action.insightId,
      );
    }
    case 'action_success_revoke': {
      return withList(
        state,
        (data) => {
          const revoked = data.insights.find((item) => item.id === action.insightId);
          return {
            ...data,
            insights: data.insights.filter((item) => item.id !== action.insightId),
            confirmedCount:
              revoked?.status === 'confirmed'
                ? Math.max(0, data.confirmedCount - 1)
                : data.confirmedCount,
          };
        },
        action.insightId,
      );
    }
    case 'action_error': {
      const insightId = action.insightId;
      const nextErrors = { ...state.actionErrorsByInsightId };
      if (insightId) {
        nextErrors[insightId] = action.error;
      }
      return {
        ...state,
        actionInsightId: null,
        actionType: null,
        actionError: action.error,
        actionErrorsByInsightId: nextErrors,
      };
    }
    case 'clear_action_error': {
      if (action.insightId) {
        const nextErrors = { ...state.actionErrorsByInsightId };
        delete nextErrors[action.insightId];
        return {
          ...state,
          actionErrorsByInsightId: nextErrors,
          actionError: Object.values(nextErrors)[0] ?? null,
        };
      }
      return {
        ...state,
        actionError: null,
        actionErrorsByInsightId: {},
      };
    }
    default:
      return state;
  }
}
