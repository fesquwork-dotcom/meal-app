import { useCallback, useEffect, useRef, useState } from 'react';

import { getStrategyById } from '@/api/strategy';
import {
  createInitialAsyncResourceState,
  createResourceRequestController,
  createResourceSessionStore,
  getResourceRetryDescriptor,
  hasResourceData,
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
import type { AsyncResourceState } from '@/features/async-resource';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';
import type { StrategyByIdResponse } from '@/types/strategy';

const RESOURCE = 'strategy_by_id';
const POLICY = RESOURCE_FRESHNESS_POLICIES.strategyById;

const stores = new Map<string, ReturnType<typeof createResourceSessionStore<StrategyByIdResponse>>>();

function storeFor(strategyId: string) {
  let store = stores.get(strategyId);
  if (!store) {
    store = createResourceSessionStore<StrategyByIdResponse>();
    stores.set(strategyId, store);
  }
  return store;
}

/**
 * Loads a persisted strategy by id.
 * Initial/refresh 404 clears cache. Refresh 5xx preserves previous data.
 */
export function useStrategyById(strategyId: string | null | undefined, enabled = true) {
  const [resource, setResource] = useState(() =>
    strategyId ? storeFor(strategyId).read() : createInitialAsyncResourceState<StrategyByIdResponse>(),
  );
  const resourceRef = useRef(resource);
  resourceRef.current = resource;
  const controllerRef = useRef(createResourceRequestController());
  const strategyIdRef = useRef(strategyId);
  strategyIdRef.current = strategyId;

  const persist = useCallback(
    (next: AsyncResourceState<StrategyByIdResponse>, id: string | null | undefined) => {
      setResource(next);
      resourceRef.current = next;
      if (id) {
        storeFor(id).write(next);
      }
    },
    [],
  );

  const reload = useCallback(async () => {
    const id = strategyIdRef.current;
    if (!enabled || !id || controllerRef.current.isDisposed) {
      if (!id) {
        persist(createInitialAsyncResourceState(), id);
      }
      return;
    }

    const hadPrevious = resourceRef.current.data !== null;
    const { requestId, signal } = controllerRef.current.begin('superseded');
    persist(
      hadPrevious
        ? {
            status: 'refreshing',
            data: resourceRef.current.data as StrategyByIdResponse,
            error: null,
            lastUpdatedAt: resourceRef.current.lastUpdatedAt ?? Date.now(),
            requestId,
          }
        : {
            status: 'loading',
            data: null,
            error: null,
            lastUpdatedAt: null,
            requestId,
          },
      id,
    );
    logResourceLoadStarted(RESOURCE, requestId);

    try {
      const response = await getStrategyById(id, { signal });
      if (!controllerRef.current.isCurrent(requestId) || strategyIdRef.current !== id) {
        logResourceResponseIgnored(RESOURCE, requestId, controllerRef.current.currentRequestId);
        return;
      }
      persist(
        {
          status: 'ready',
          data: response,
          error: null,
          lastUpdatedAt: Date.now(),
          requestId,
        },
        id,
      );
      logResourceLoadSucceeded(RESOURCE, requestId);
    } catch (err: unknown) {
      if (isRequestAbortError(err)) {
        return;
      }
      if (!controllerRef.current.isCurrent(requestId) || strategyIdRef.current !== id) {
        logResourceResponseIgnored(RESOURCE, requestId, controllerRef.current.currentRequestId);
        return;
      }
      const error = classifyStrategyWorkflowError(err);
      const clearOnNotFound = error.kind === 'not_found';
      const preserve = hadPrevious && !clearOnNotFound;
      persist(
        {
          status: 'error',
          data: preserve ? resourceRef.current.data : null,
          error,
          lastUpdatedAt: preserve ? resourceRef.current.lastUpdatedAt : null,
          requestId,
        },
        id,
      );
      if (clearOnNotFound) {
        storeFor(id).clear();
      }
      logResourceLoadFailed(RESOURCE, requestId, error, preserve);
    }
  }, [enabled, persist]);

  useEffect(() => {
    const controller = createResourceRequestController();
    controllerRef.current = controller;

    if (!enabled || !strategyId) {
      persist(createInitialAsyncResourceState(), strategyId);
      return () => controller.dispose();
    }

    const cached = storeFor(strategyId).read();
    persist(cached, strategyId);
    resourceRef.current = cached;

    const now = Date.now();
    const freshness = selectResourceFreshness(cached, POLICY, now);
    if (!shouldLoadResourceOnMount(cached, POLICY, now)) {
      logResourceCacheHit(RESOURCE, freshness);
      return () => controller.dispose();
    }
    if (hasResourceData(cached) && freshness === 'stale') {
      logResourceCacheStale(RESOURCE, freshness);
    }
    void reload();
    return () => controller.dispose();
  }, [enabled, strategyId, reload, persist]);

  return {
    resource,
    data: resource.data,
    isLoading: isInitialLoading(resource) && !hasResourceData(resource),
    isRefreshing: isRefreshing(resource),
    isRefreshError: isRefreshError(resource),
    freshness: selectResourceFreshness(resource, POLICY, Date.now()),
    error: resourceError(resource),
    retry: getResourceRetryDescriptor(resource),
    reload,
  };
}
