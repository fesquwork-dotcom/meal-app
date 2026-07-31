import type { AsyncResourceState } from '@/features/async-resource/types';
import type { ResourceFreshness } from '@/features/async-resource/resourceFreshnessPolicy';
import {
  canRetryResource,
  hasResourceData,
  isInitialLoadError,
  isInitialLoading,
  isRefreshError,
  isRefreshing,
} from '@/features/async-resource/asyncResourceSelectors';
import { getResourceRetryDescriptor } from '@/features/async-resource/resourceRetryDescriptor';

export interface AsyncResourceViewModel {
  showInitialLoader: boolean;
  showFullError: boolean;
  showData: boolean;
  showRefreshingIndicator: boolean;
  showRefreshError: boolean;
  retryEnabled: boolean;
  freshness: ResourceFreshness;
}

export function buildAsyncResourceViewModel<T>(
  state: AsyncResourceState<T>,
  freshness: ResourceFreshness,
): AsyncResourceViewModel {
  const retry = getResourceRetryDescriptor(state);
  const pending = isRefreshing(state) || (isInitialLoading(state) && !hasResourceData(state));
  return {
    showInitialLoader: isInitialLoading(state) && !hasResourceData(state),
    showFullError: isInitialLoadError(state),
    showData: hasResourceData(state),
    showRefreshingIndicator: isRefreshing(state),
    showRefreshError: isRefreshError(state),
    retryEnabled: canRetryResource(state) && !pending && retry.enabled,
    freshness,
  };
}
