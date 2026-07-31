import type { ServerPreviewStaleReason } from '@/features/strategy-inputs/types';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';

export interface StaleRoutingResult {
  routed: boolean;
  staleReason: ServerPreviewStaleReason | null;
}

/**
 * Routes stale workflow errors to StrategyInputsCoordinator.
 * Non-stale errors must not call notifyPreviewBecameStale.
 */
export function routeStaleWorkflowError(
  error: StrategyWorkflowError,
  notifyPreviewBecameStale: (reason: ServerPreviewStaleReason) => void,
): StaleRoutingResult {
  if (error.kind !== 'stale' || !error.staleReason) {
    return { routed: false, staleReason: null };
  }
  if (import.meta.env.DEV) {
    console.info('strategy_workflow_stale_routed', {
      kind: error.kind,
      code: error.code,
      retryable: error.retryable,
      http_status: error.originalStatus,
    });
  }
  notifyPreviewBecameStale(error.staleReason);
  return { routed: true, staleReason: error.staleReason };
}

export function logWorkflowErrorClassified(error: StrategyWorkflowError): void {
  if (import.meta.env.PROD) {
    return;
  }
  console.info('strategy_workflow_error_classified', {
    kind: error.kind,
    code: error.code,
    retryable: error.retryable,
    requires_new_preview: error.requiresNewPreview,
    requires_profile_action: error.requiresProfileAction,
    http_status: error.originalStatus,
  });
}
