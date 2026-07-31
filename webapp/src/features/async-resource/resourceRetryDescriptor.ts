import type { AsyncResourceState } from '@/features/async-resource/types';
import { canRetryResource, isRefreshing } from '@/features/async-resource/asyncResourceSelectors';

export interface ResourceRetryDescriptor {
  action: 'reload_resource';
  label: string;
  enabled: boolean;
}

const RETRY_LABEL = 'Повторить';

/** Typed retry for resource loads — not strategy workflow actions. */
export function getResourceRetryDescriptor<T>(
  state: AsyncResourceState<T>,
): ResourceRetryDescriptor {
  return {
    action: 'reload_resource',
    label: RETRY_LABEL,
    enabled: canRetryResource(state) && !isRefreshing(state),
  };
}
