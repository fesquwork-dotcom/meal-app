import type { GenerationJob } from '@/types/api';
import {
  resolveStrategyWorkflowMessage,
} from '@/features/strategy-workflow/strategyWorkflowErrorMessages';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';

const GENERATION_JOB_ERROR_CODES = new Set([
  'MENU_GENERATION_INVALID',
  'MENU_GENERATION_OUTPUT_TRUNCATED',
  'MENU_GENERATION_TIMEOUT',
  'MENU_GENERATION_UNAVAILABLE',
  'GENERATION_INTERRUPTED',
  'GENERATION_FAILED',
  'GENERATION_SAVE_FAILED',
]);

/**
 * Map a terminal generation job failure to a safe workflow error.
 * Uses error_code for copy resolution — never classifies raw Error(message)
 * as CLIENT_UNKNOWN_ERROR (which previously overwrote good safe_message).
 */
export function classifyGenerationJobFailure(job: GenerationJob): StrategyWorkflowError {
  const code = (job.error_code || 'GENERATION_FAILED').trim() || 'GENERATION_FAILED';
  const backendMessage = job.safe_message?.trim() || null;
  const kind =
    code === 'MENU_GENERATION_UNAVAILABLE' || code === 'MENU_GENERATION_TIMEOUT'
      ? 'service_unavailable'
      : code === 'GENERATION_INTERRUPTED'
        ? 'retryable'
        : 'retryable';

  const message = resolveStrategyWorkflowMessage({
    code: GENERATION_JOB_ERROR_CODES.has(code) ? code : 'GENERATION_FAILED',
    kind,
    backendMessage,
  });

  return {
    kind,
    code: GENERATION_JOB_ERROR_CODES.has(code) ? code : 'GENERATION_FAILED',
    message,
    fieldErrors: [],
    retryable: true,
    requiresNewPreview: false,
    requiresProfileAction: false,
    staleReason: null,
    requestId: null,
    originalStatus: null,
  };
}
