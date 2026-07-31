import { useCallback, useEffect, useRef, useState } from 'react';

import {
  confirmMemorySignal,
  dismissMemorySignal,
  getMemorySignals,
  promoteMemorySignal,
} from '@/api/memory';
import {
  createResourceRequestController,
  createResourceSessionStore,
  getResourceRetryDescriptor,
  hasResourceData,
  isRequestAbortError,
  isRefreshing,
  isRefreshError,
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
  startResourceLoad,
} from '@/features/async-resource';
import type { AsyncResourceState } from '@/features/async-resource';
import {
  classifyStrategyWorkflowError,
  logWorkflowErrorClassified,
} from '@/features/strategy-workflow';
import type {
  MemoryPromotionResult,
  MemorySignalActionResult,
} from '@/features/strategy-workflow/workflowSuccessTypes';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';
import type { MemorySignal } from '@/types/memory';

export type MemorySignalsList = MemorySignal[];

const RESOURCE = 'memory_signals';
const POLICY = RESOURCE_FRESHNESS_POLICIES.memory;
const sessionStore = createResourceSessionStore<MemorySignalsList>();

/**
 * Loads and mutates preference signals.
 * SPA session store preserves list across Profile remounts for freshness cache hits.
 */
export function useMemorySignals(enabled = true) {
  const [resource, setResource] = useState(() => sessionStore.read());
  const resourceRef = useRef(resource);
  resourceRef.current = resource;
  const [actionErrorsBySignalId, setActionErrorsBySignalId] = useState<
    Record<string, StrategyWorkflowError>
  >({});
  const [promotionError, setPromotionError] = useState<StrategyWorkflowError | null>(null);
  const controllerRef = useRef(createResourceRequestController());

  const persist = useCallback((next: AsyncResourceState<MemorySignalsList>) => {
    setResource(next);
    resourceRef.current = next;
    sessionStore.write(next);
  }, []);

  const reload = useCallback(
    async (force = true) => {
      if (!enabled || controllerRef.current.isDisposed) {
        return;
      }
      if (!force && isRefreshing(resourceRef.current)) {
        return;
      }

      const hadPrevious = resourceRef.current.data !== null;
      const { requestId, signal } = controllerRef.current.begin('superseded');
      const started = startResourceLoad(resourceRef.current);
      // Align session requestId with controller id.
      const loadingState =
        hadPrevious
          ? {
              status: 'refreshing' as const,
              data: resourceRef.current.data as MemorySignalsList,
              error: null,
              lastUpdatedAt: resourceRef.current.lastUpdatedAt ?? Date.now(),
              requestId,
            }
          : {
              status: 'loading' as const,
              data: null,
              error: null,
              lastUpdatedAt: null,
              requestId,
            };
      persist(loadingState);
      logResourceLoadStarted(RESOURCE, requestId);
      if (import.meta.env.DEV && hadPrevious) {
        console.info('resource_refresh_started', { resource: RESOURCE, requestId });
      }
      void started;

      try {
        const signals = await getMemorySignals({ signal });
        if (!controllerRef.current.isCurrent(requestId)) {
          logResourceResponseIgnored(RESOURCE, requestId, controllerRef.current.currentRequestId);
          return;
        }
        const next: AsyncResourceState<MemorySignalsList> = {
          status: 'ready',
          data: signals,
          error: null,
          lastUpdatedAt: Date.now(),
          requestId,
        };
        persist(next);
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
        const next: AsyncResourceState<MemorySignalsList> = {
          status: 'error',
          data: hadPrevious ? resourceRef.current.data : null,
          error,
          lastUpdatedAt: hadPrevious ? resourceRef.current.lastUpdatedAt : null,
          requestId,
        };
        persist(next);
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
    },
    [enabled, persist],
  );

  useEffect(() => {
    const controller = createResourceRequestController();
    controllerRef.current = controller;
    if (!enabled) {
      return () => controller.dispose();
    }

    const now = Date.now();
    const current = resourceRef.current;
    const freshness = selectResourceFreshness(current, POLICY, now);
    if (!shouldLoadResourceOnMount(current, POLICY, now)) {
      logResourceCacheHit(RESOURCE, freshness);
      return () => controller.dispose();
    }
    if (hasResourceData(current) && freshness === 'stale') {
      logResourceCacheStale(RESOURCE, freshness);
    }
    void reload(true);
    return () => {
      controller.dispose();
    };
  }, [enabled, reload]);

  const setCardError = useCallback((signalId: string, error: StrategyWorkflowError | null) => {
    setActionErrorsBySignalId((prev) => {
      if (!error) {
        if (!(signalId in prev)) {
          return prev;
        }
        const next = { ...prev };
        delete next[signalId];
        return next;
      }
      return { ...prev, [signalId]: error };
    });
  }, []);

  const applyLocalSignals = useCallback(
    (nextSignals: MemorySignalsList) => {
      const current = resourceRef.current;
      const next: AsyncResourceState<MemorySignalsList> = {
        status: 'ready',
        data: nextSignals,
        error: null,
        lastUpdatedAt: Date.now(),
        requestId: current.requestId,
      };
      persist(next);
      setActionErrorsBySignalId((prev) => {
        const ids = new Set(nextSignals.map((item) => item.id));
        let changed = false;
        const cleaned: Record<string, StrategyWorkflowError> = {};
        for (const [id, err] of Object.entries(prev)) {
          if (ids.has(id)) {
            cleaned[id] = err;
          } else {
            changed = true;
          }
        }
        return changed ? cleaned : prev;
      });
    },
    [persist],
  );

  const confirm = useCallback(
    async (signalId: string): Promise<MemorySignalActionResult> => {
      setCardError(signalId, null);
      try {
        await confirmMemorySignal(signalId);
        await reload(true);
        if (import.meta.env.DEV) {
          console.info('workflow_action_succeeded', { domain: 'memory', action: 'confirm' });
        }
        return { ok: true, data: { signalId, wasConfirmed: false } };
      } catch (err: unknown) {
        const workflowError = classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(workflowError);
        setCardError(signalId, workflowError);
        return { ok: false, error: workflowError };
      }
    },
    [reload, setCardError],
  );

  const dismiss = useCallback(
    async (signalId: string): Promise<MemorySignalActionResult> => {
      setCardError(signalId, null);
      const existing = (resourceRef.current.data ?? []).find((item) => item.id === signalId);
      const wasConfirmed = existing?.status === 'confirmed';
      try {
        await dismissMemorySignal(signalId);
        const previous = resourceRef.current.data ?? [];
        applyLocalSignals(previous.filter((item) => item.id !== signalId));
        if (import.meta.env.DEV) {
          console.info('workflow_action_succeeded', { domain: 'memory', action: 'dismiss' });
        }
        return { ok: true, data: { signalId, wasConfirmed } };
      } catch (err: unknown) {
        const workflowError = classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(workflowError);
        setCardError(signalId, workflowError);
        return { ok: false, error: workflowError };
      }
    },
    [applyLocalSignals, setCardError],
  );

  const promote = useCallback(
    async (
      signalId: string,
      expectedProfileRevision: number,
    ): Promise<MemoryPromotionResult> => {
      setPromotionError(null);
      setCardError(signalId, null);
      try {
        const result = await promoteMemorySignal(signalId, expectedProfileRevision);
        if (import.meta.env.DEV) {
          console.info('workflow_action_succeeded', { domain: 'memory', action: 'promote' });
        }
        return {
          ok: true,
          data: {
            profile: result.profile,
            revision: result.revision,
            promotionStatus: result.promotionStatus,
          },
        };
      } catch (err: unknown) {
        const workflowError = classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(workflowError);
        setPromotionError(workflowError);
        setCardError(signalId, workflowError);
        return { ok: false, error: workflowError };
      }
    },
    [setCardError],
  );

  const clearActionError = useCallback((signalId?: string) => {
    if (signalId) {
      setCardError(signalId, null);
      return;
    }
    setActionErrorsBySignalId({});
    setPromotionError(null);
  }, [setCardError]);

  const signals = resource.data ?? [];
  const loadError = resourceError(resource);
  const retry = getResourceRetryDescriptor(resource);
  const now = Date.now();
  const freshness = selectResourceFreshness(resource, POLICY, now);

  /** Compat: last card error or promotion error for legacy section panels. */
  const actionError =
    promotionError ??
    (Object.keys(actionErrorsBySignalId).length > 0
      ? actionErrorsBySignalId[Object.keys(actionErrorsBySignalId)[0]!]
      : null);

  return {
    resource,
    signals,
    isLoading: resource.status === 'loading',
    isRefreshing: isRefreshing(resource),
    isRefreshError: isRefreshError(resource),
    freshness,
    error: loadError,
    actionError,
    actionErrorsBySignalId,
    promotionError,
    reload: () => reload(true),
    retry,
    confirm,
    dismiss,
    promote,
    clearActionError,
  };
}
