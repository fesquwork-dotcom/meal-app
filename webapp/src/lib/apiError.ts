import { classifyStrategyWorkflowError } from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import { buildProfileFieldErrorMap } from '@/features/strategy-workflow/strategyWorkflowFieldMapping';
import type { ApiFieldError } from '@/types/api';
import axios from 'axios';

/**
 * Low-level string extractor for casual call sites.
 * Strategy workflow surfaces should prefer classifyStrategyWorkflowError.
 */
export function parseApiError(err: unknown): string {
  return classifyStrategyWorkflowError(err).message;
}

/** Returns field-level validation errors when the unified envelope is present. */
export function parseApiFieldErrors(err: unknown): ApiFieldError[] {
  const classified = classifyStrategyWorkflowError(err);
  return classified.fieldErrors.map((item) => ({
    field: item.field,
    code: item.code,
    message: item.message,
  }));
}

/** Maps `profile.<field>` errors to a simple field → message record for forms. */
export function profileFieldErrors(err: unknown): Record<string, string> {
  return buildProfileFieldErrorMap(classifyStrategyWorkflowError(err).fieldErrors);
}

/** @deprecated Prefer classifyStrategyWorkflowError — kept for transitional imports only. */
export function isAxiosTransportError(err: unknown): boolean {
  return axios.isAxiosError(err);
}
