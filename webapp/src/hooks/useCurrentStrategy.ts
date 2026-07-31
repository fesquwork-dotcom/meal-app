import { useCallback, useEffect, useRef, useState } from 'react';

import { getCurrentStrategy } from '@/api/strategy';
import {
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
import type { CurrentStrategyResponse } from '@/types/strategy';

const RESOURCE = 'strategy_current';
const POLICY = RESOURCE_FRESHNESS_POLICIES.currentStrategy;
const sessionStore = createResourceSessionStore<CurrentStrategyResponse>();

/** Loads current weekly strategy from backend. */
export function useCurrentStrategy(enabled = true) {
  const [resource, setResource] = useState(() => sessionStore.read());
  const resourceRef = useRef(resource);
  resourceRef.current = resource;
  const controllerRef = useRef(createResourceRequestController());

  const persist = useCallback((next: AsyncResourceState<CurrentStrategyResponse>) => {
    setResource(next);
    resourceRef.current = next;
    sessionStore.write(next);
  }, []);

  const reload = useCallback(async () => {
    if (!enabled || controllerRef.current.isDisposed) {
      return;
    }
    const hadPrevious = resourceRef.current.data !== null;
    const { requestId, signal } = controllerRef.current.begin('superseded');
    persist(
      hadPrevious
        ? {
            status: 'refreshing',
            data: resourceRef.current.data as CurrentStrategyResponse,
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
    );
    logResourceLoadStarted(RESOURCE, requestId);
    try {
      const response = await getCurrentStrategy({ signal });
      if (!controllerRef.current.isCurrent(requestId)) {
        logResourceResponseIgnored(RESOURCE, requestId, controllerRef.current.currentRequestId);
        return;
      }
      persist({
        status: 'ready',
        data: response,
        error: null,
        lastUpdatedAt: Date.now(),
        requestId,
      });
      logResourceLoadSucceeded(RESOURCE, requestId);
    } catch (err: unknown) {
      if (isRequestAbortError(err)) {
        return;
      }
      if (!controllerRef.current.isCurrent(requestId)) {
        logResourceResponseIgnored(RESOURCE, requestId, controllerRef.current.currentRequestId);
        return;
      }
      const error = classifyStrategyWorkflowError(err);
      persist({
        status: 'error',
        data: hadPrevious ? resourceRef.current.data : null,
        error,
        lastUpdatedAt: hadPrevious ? resourceRef.current.lastUpdatedAt : null,
        requestId,
      });
      logResourceLoadFailed(RESOURCE, requestId, error, hadPrevious);
    }
  }, [enabled, persist]);

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
    void reload();
    return () => controller.dispose();
  }, [enabled, reload]);

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
