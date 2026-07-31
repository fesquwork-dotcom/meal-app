import type { ServerPreviewStaleReason } from '@/features/strategy-inputs/types';

export type StrategyWorkflowErrorKind =
  | 'stale'
  | 'validation'
  | 'conflict'
  | 'retryable'
  | 'authentication'
  | 'not_found'
  | 'rate_limited'
  | 'service_unavailable'
  | 'fatal'
  | 'unknown';

export interface StrategyWorkflowFieldError {
  field: string;
  code: string;
  message: string;
}

export interface StrategyWorkflowError {
  kind: StrategyWorkflowErrorKind;
  code: string;
  message: string;
  fieldErrors: StrategyWorkflowFieldError[];
  retryable: boolean;
  requiresNewPreview: boolean;
  requiresProfileAction: boolean;
  staleReason: ServerPreviewStaleReason | null;
  requestId: string | null;
  originalStatus: number | null;
}

export type WorkflowResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: StrategyWorkflowError };

export type GenerateMenuWorkflowResult =
  | { ok: true; menuPlan: import('@/types/menu').MenuPlan }
  | { ok: false; error: StrategyWorkflowError };

export type WorkflowRetryAction =
  | 'retry_same_request'
  | 'build_new_preview'
  | 'open_profile'
  | 'reload_profile'
  | 'restart_app'
  | 'none';

export const WORKFLOW_ERROR_CODES = {
  NETWORK: 'CLIENT_NETWORK_ERROR',
  TIMEOUT: 'CLIENT_TIMEOUT',
  UNKNOWN: 'CLIENT_UNKNOWN_ERROR',
  RATE_LIMITED: 'CLIENT_RATE_LIMITED',
} as const;
