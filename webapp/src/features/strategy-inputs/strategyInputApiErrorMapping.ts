import { classifyStrategyWorkflowError } from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import type { StrategyInputChangeReason } from '@/features/strategy-inputs/types';

/**
 * Maps API failures to coordinator stale reasons.
 * Prefer classifyStrategyWorkflowError().staleReason for full typing.
 */
export function mapApiErrorToStrategyInputChangeReason(
  error: unknown,
): StrategyInputChangeReason | null {
  return classifyStrategyWorkflowError(error).staleReason;
}

/** @deprecated Prefer classifyStrategyWorkflowError */
export function extractApiErrorCode(err: unknown): string | null {
  const classified = classifyStrategyWorkflowError(err);
  if (classified.code.startsWith('CLIENT_')) {
    return null;
  }
  return classified.code;
}
