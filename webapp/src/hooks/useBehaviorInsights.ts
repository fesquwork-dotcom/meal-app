import { useCallback, useEffect, useReducer, useRef } from 'react';

import {
  applyBehaviorRecommendation,
  confirmBehaviorInsight,
  dismissBehaviorInsight,
  getBehaviorInsights,
  revokeBehaviorInsight,
  snoozeBehaviorInsight,
} from '@/api/behavior';
import {
  behaviorInsightsReducer,
  initialBehaviorInsightsState,
  mapListResponse,
  type BehaviorInsightsListData,
  type BehaviorInsightsState,
} from '@/features/behavior/behaviorInsightsState';
import {
  createResourceRequestController,
  createResourceSessionStore,
  getResourceRetryDescriptor,
  hasResourceData,
  isInitialLoadError,
  isInitialLoading,
  isRefreshError,
  isRefreshing,
  isRequestAbortError,
  logResourceCacheHit,
  logResourceCacheStale,
  logResourceLoadFailed,
  logResourceLoadStarted,
  logResourceLoadSucceeded,
  logResourceResponseIgnored,
  RESOURCE_FRESHNESS_POLICIES,
  resourceError,
  selectResourceFreshness,
  shouldLoadResourceOnMount,
} from '@/features/async-resource';
import {
  classifyStrategyWorkflowError,
  logWorkflowErrorClassified,
} from '@/features/strategy-workflow';
import type {
  BehaviorInsightActionResult,
  BehaviorRecommendationResult,
} from '@/features/strategy-workflow/workflowSuccessTypes';
import type { BehaviorSnoozeDuration } from '@/types/behavior';

const RESOURCE = 'behavior_insights';
const POLICY = RESOURCE_FRESHNESS_POLICIES.behavior;
const sessionStore = createResourceSessionStore<BehaviorInsightsListData>();

function withSessionResource(state: BehaviorInsightsState): BehaviorInsightsState {
  return { ...state, resource: sessionStore.read() };
}

/** Loads and mutates behavior insights for the Profile observations section. */
export function useBehaviorInsights(enabled = true) {
  const [state, dispatch] = useReducer(
    behaviorInsightsReducer,
    undefined,
    () => withSessionResource(initialBehaviorInsightsState),
  );
  const stateRef = useRef(state);
  stateRef.current = state;
  const controllerRef = useRef(createResourceRequestController());

  useEffect(() => {
    sessionStore.write(state.resource);
  }, [state.resource]);

  const refresh = useCallback(async () => {
    if (!enabled || controllerRef.current.isDisposed) {
      return;
    }
    const hadPrevious = stateRef.current.resource.data !== null;
    const { requestId, signal } = controllerRef.current.begin('superseded');
    dispatch({
      type: 'resource',
      action: hadPrevious
        ? { type: 'refresh_started', requestId }
        : { type: 'load_started', requestId },
    });
    logResourceLoadStarted(RESOURCE, requestId);
    if (import.meta.env.DEV && hadPrevious) {
      console.info('resource_refresh_started', { resource: RESOURCE, requestId });
    }
    try {
      const payload = await getBehaviorInsights({ signal });
      if (!controllerRef.current.isCurrent(requestId)) {
        logResourceResponseIgnored(RESOURCE, requestId, controllerRef.current.currentRequestId);
        return;
      }
      dispatch({
        type: 'resource',
        action: {
          type: hadPrevious ? 'refresh_succeeded' : 'load_succeeded',
          requestId,
          data: mapListResponse(payload),
        },
      });
      logResourceLoadSucceeded(RESOURCE, requestId);
      if (import.meta.env.DEV && hadPrevious) {
        console.info('resource_refresh_succeeded', { resource: RESOURCE, requestId });
      }
    } catch (err: unknown) {
      if (isRequestAbortError(err)) {
        return;
      }
      if (!controllerRef.current.isCurrent(requestId)) {
        logResourceResponseIgnored(RESOURCE, requestId, controllerRef.current.currentRequestId);
        return;
      }
      const error = classifyStrategyWorkflowError(err);
      dispatch({
        type: 'resource',
        action: {
          type: hadPrevious ? 'refresh_failed' : 'load_failed',
          requestId,
          error,
        },
      });
      logResourceLoadFailed(RESOURCE, requestId, error, hadPrevious);
      if (import.meta.env.DEV && hadPrevious) {
        console.info('resource_refresh_failed_with_cache', {
          resource: RESOURCE,
          requestId,
          kind: error.kind,
          code: error.code,
        });
      }
    }
  }, [enabled]);

  useEffect(() => {
    const controller = createResourceRequestController();
    controllerRef.current = controller;
    if (!enabled) {
      return () => controller.dispose();
    }
    const now = Date.now();
    const current = stateRef.current.resource;
    const freshness = selectResourceFreshness(current, POLICY, now);
    if (!shouldLoadResourceOnMount(current, POLICY, now)) {
      logResourceCacheHit(RESOURCE, freshness);
      return () => controller.dispose();
    }
    if (hasResourceData(current) && freshness === 'stale') {
      logResourceCacheStale(RESOURCE, freshness);
    }
    void refresh();
    return () => {
      controller.dispose();
    };
  }, [enabled, refresh]);

  const confirm = useCallback(async (insightId: string): Promise<BehaviorInsightActionResult> => {
    dispatch({ type: 'action_start', insightId, actionType: 'confirm' });
    try {
      const insight = await confirmBehaviorInsight(insightId);
      dispatch({ type: 'action_success_confirm', insight });
      return { ok: true, data: { insight } };
    } catch (err: unknown) {
      const error = classifyStrategyWorkflowError(err);
      logWorkflowErrorClassified(error);
      dispatch({ type: 'action_error', error, insightId });
      return { ok: false, error };
    }
  }, []);

  const dismiss = useCallback(async (insightId: string): Promise<BehaviorInsightActionResult> => {
    dispatch({ type: 'action_start', insightId, actionType: 'dismiss' });
    try {
      const insight = await dismissBehaviorInsight(insightId);
      dispatch({ type: 'action_success_dismiss', insightId });
      return { ok: true, data: { insight } };
    } catch (err: unknown) {
      const error = classifyStrategyWorkflowError(err);
      logWorkflowErrorClassified(error);
      dispatch({ type: 'action_error', error, insightId });
      return { ok: false, error };
    }
  }, []);

  const snooze = useCallback(
    async (
      insightId: string,
      duration: BehaviorSnoozeDuration,
    ): Promise<BehaviorInsightActionResult> => {
      dispatch({ type: 'action_start', insightId, actionType: 'snooze' });
      try {
        const insight = await snoozeBehaviorInsight(insightId, duration);
        dispatch({ type: 'action_success_snooze', insightId });
        return {
          ok: true,
          data: { insight, snoozedUntil: insight.snoozed_until ?? null },
        };
      } catch (err: unknown) {
        const error = classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(error);
        dispatch({ type: 'action_error', error, insightId });
        return { ok: false, error };
      }
    },
    [],
  );

  const revoke = useCallback(
    async (insightId: string): Promise<BehaviorInsightActionResult> => {
      dispatch({ type: 'action_start', insightId, actionType: 'revoke' });
      try {
        const result = await revokeBehaviorInsight(insightId);
        dispatch({ type: 'action_success_revoke', insightId });
        return {
          ok: true,
          data: {
            insight: result.insight,
            strategyEffectChanged: result.strategy_effect_changed,
            profilePreferenceRemainsActive: result.profile_preference_remains_active,
          },
        };
      } catch (err: unknown) {
        const error = classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(error);
        dispatch({ type: 'action_error', error, insightId });
        return { ok: false, error };
      }
    },
    [],
  );

  const applyRecommendation = useCallback(
    async (
      insightId: string,
      expectedProfileRevision: number,
    ): Promise<BehaviorRecommendationResult> => {
      dispatch({ type: 'action_start', insightId, actionType: 'apply_recommendation' });
      try {
        const result = await applyBehaviorRecommendation(insightId, expectedProfileRevision);
        const payload = await getBehaviorInsights();
        const requestId = stateRef.current.resource.requestId;
        dispatch({
          type: 'resource',
          action: {
            type: 'refresh_succeeded',
            requestId,
            data: mapListResponse(payload),
          },
        });
        return {
          ok: true,
          data: {
            profile: result.profile,
            revision: result.revision,
            recommendationStatus: result.recommendationStatus,
            recommendationKey: result.recommendationKey,
            insight: payload.insights.find((item) => item.id === insightId),
          },
        };
      } catch (err: unknown) {
        const error = classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(error);
        dispatch({ type: 'action_error', error, insightId });
        return { ok: false, error };
      }
    },
    [],
  );

  const clearActionError = useCallback((insightId?: string) => {
    dispatch({ type: 'clear_action_error', insightId });
  }, []);

  const resource = state.resource;
  const list = resource.data;
  const loadError = resourceError(resource);
  const retry = getResourceRetryDescriptor(resource);
  const freshness = selectResourceFreshness(resource, POLICY, Date.now());

  return {
    status: resource.status,
    resource,
    insights: list?.insights ?? [],
    candidateCount: list?.candidateCount ?? 0,
    confirmedCount: list?.confirmedCount ?? 0,
    actionInsightId: state.actionInsightId,
    actionType: state.actionType,
    loadError,
    actionError: state.actionError,
    actionErrorsByInsightId: state.actionErrorsByInsightId,
    isLoading: isInitialLoading(resource) && !hasResourceData(resource),
    isRefreshing: isRefreshing(resource),
    isInitialLoadError: isInitialLoadError(resource),
    isRefreshError: isRefreshError(resource),
    freshness,
    retry,
    refresh,
    confirm,
    dismiss,
    snooze,
    revoke,
    applyRecommendation,
    clearActionError,
  };
}
