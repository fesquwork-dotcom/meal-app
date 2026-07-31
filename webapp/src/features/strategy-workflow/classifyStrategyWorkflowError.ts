import axios from 'axios';
import type { ApiErrorResponse, ApiFieldError } from '@/types/api';
import type { ServerPreviewStaleReason } from '@/features/strategy-inputs/types';
import { resolveStrategyWorkflowMessage } from '@/features/strategy-workflow/strategyWorkflowErrorMessages';
import type {
  StrategyWorkflowError,
  StrategyWorkflowErrorKind,
  StrategyWorkflowFieldError,
} from '@/features/strategy-workflow/types';
import { WORKFLOW_ERROR_CODES } from '@/features/strategy-workflow/types';

const STALE_CODE_TO_REASON: Record<string, ServerPreviewStaleReason> = {
  STRATEGY_PREVIEW_STALE_PROFILE: 'server_stale_profile',
  STRATEGY_PREVIEW_STALE_MEMORY: 'server_stale_memory',
  STRATEGY_PREVIEW_STALE_BEHAVIOR: 'server_stale_behavior',
  STRATEGY_PREVIEW_STALE_LEARNED_PREFERENCES:
    'server_stale_learned_preferences',
  STRATEGY_PREVIEW_STALE: 'server_stale_generic',
  STRATEGY_PREVIEW_VERSION_MISMATCH: 'preview_version_mismatch',
  STRATEGY_PREVIEW_EXPIRED: 'preview_token_expired',
  STRATEGY_PREVIEW_INVALID: 'preview_token_invalid',
  STRATEGY_PREVIEW_TOKEN_MISSING: 'preview_token_invalid',
  STRATEGY_PREVIEW_REQUIRED: 'preview_token_invalid',
};

const VALIDATION_CODES = new Set([
  'REQUEST_VALIDATION_ERROR',
  'PROFILE_REQUIRED',
  'PROFILE_INVALID',
  'PROFILE_INCOMPLETE',
  'PROFILE_PROTEIN_REQUIRED',
  'PROFILE_PROTEIN_EXCLUDED',
  'PROFILE_ANY_WITH_SPECIFIC_PROTEINS',
  'PROFILE_TOO_MANY_CONSTRAINTS',
  'PROFILE_CONSTRAINT_VALUE_EMPTY',
  'PROFILE_CONSTRAINT_ID_INVALID',
  'PERSISTED_PROFILE_INVALID',
  'NO_ALLOWED_PREFERRED_PROTEINS',
  'BEHAVIOR_SNOOZE_DURATION_INVALID',
]);

const PROFILE_ACTION_CODES = new Set([
  'PROFILE_REQUIRED',
  'PROFILE_INVALID',
  'PROFILE_INCOMPLETE',
  'PROFILE_PROTEIN_REQUIRED',
  'PROFILE_PROTEIN_EXCLUDED',
  'PROFILE_ANY_WITH_SPECIFIC_PROTEINS',
  'PROFILE_TOO_MANY_CONSTRAINTS',
  'PROFILE_REQUIRES_PROTEIN_SELECTION',
  'PERSISTED_PROFILE_INVALID',
  'NO_ALLOWED_PREFERRED_PROTEINS',
  'REQUEST_VALIDATION_ERROR',
]);

const CONFLICT_CODES = new Set([
  'PROFILE_STALE',
  'CONFLICT_NOT_FOUND',
  'CONFLICT_ACTION_NOT_ALLOWED',
  'PROFILE_REQUIRES_PROTEIN_SELECTION',
  'CONSTRAINT_NOT_REMOVABLE',
  'MEMORY_PROMOTION_PROFILE_STALE',
  'BEHAVIOR_RECOMMENDATION_PROFILE_STALE',
]);

const RETRYABLE_CODES = new Set([
  'BEHAVIOR_SERVICE_UNAVAILABLE',
  'MEMORY_PROMOTION_FAILED',
  'STRATEGY_COMPARE_FAILED',
  'STRATEGY_SAVE_FAILED',
  'REPLACEMENT_FAILED',
  'REPLACEMENT_PRICE_UNRESOLVED',
  'BEHAVIOR_SNOOZE_FAILED',
  'BEHAVIOR_REVOKE_FAILED',
  'BEHAVIOR_RECOMMENDATION_FAILED',
  'BEHAVIOR_EVALUATION_FAILED',
  'BEHAVIOR_CONTEXT_UNAVAILABLE',
]);

const NOT_FOUND_CODES = new Set([
  'BEHAVIOR_INSIGHT_NOT_FOUND',
  'MEMORY_SIGNAL_NOT_FOUND',
  'STRATEGY_NOT_FOUND',
  'REPLACEMENT_NOT_FOUND',
]);

function isUnifiedError(body: unknown): body is ApiErrorResponse {
  return (
    !!body &&
    typeof body === 'object' &&
    'code' in body &&
    'message' in body &&
    typeof (body as ApiErrorResponse).code === 'string' &&
    typeof (body as ApiErrorResponse).message === 'string'
  );
}

function mapFieldErrors(raw: ApiFieldError[] | undefined): StrategyWorkflowFieldError[] {
  if (!raw?.length) {
    return [];
  }
  return raw.map((item) => ({
    field: item.field,
    code: item.code,
    message: item.message,
  }));
}

function classifyByCode(
  code: string,
  status: number | null,
): {
  kind: StrategyWorkflowErrorKind;
  retryable: boolean;
  requiresNewPreview: boolean;
  requiresProfileAction: boolean;
  staleReason: ServerPreviewStaleReason | null;
} {
  if (code in STALE_CODE_TO_REASON) {
    return {
      kind: 'stale',
      retryable: false,
      requiresNewPreview: true,
      requiresProfileAction: false,
      staleReason: STALE_CODE_TO_REASON[code],
    };
  }

  if (VALIDATION_CODES.has(code)) {
    return {
      kind: 'validation',
      retryable: false,
      requiresNewPreview: false,
      requiresProfileAction: PROFILE_ACTION_CODES.has(code),
      staleReason: null,
    };
  }

  if (CONFLICT_CODES.has(code)) {
    return {
      kind: 'conflict',
      retryable: false,
      requiresNewPreview: false,
      requiresProfileAction:
        code === 'PROFILE_REQUIRES_PROTEIN_SELECTION' || code === 'PROFILE_STALE',
      staleReason: null,
    };
  }

  if (NOT_FOUND_CODES.has(code)) {
    return {
      kind: 'not_found',
      retryable: false,
      requiresNewPreview: false,
      requiresProfileAction: false,
      staleReason: null,
    };
  }

  if (RETRYABLE_CODES.has(code) || status === 502 || status === 503) {
    return {
      kind: status === 503 ? 'service_unavailable' : 'retryable',
      retryable: true,
      requiresNewPreview: false,
      requiresProfileAction: false,
      staleReason: null,
    };
  }

  if (code.startsWith('BEHAVIOR_INSIGHT_NOT_') || code === 'BEHAVIOR_RECOMMENDATION_NOT_AVAILABLE') {
    return {
      kind: 'conflict',
      retryable: false,
      requiresNewPreview: false,
      requiresProfileAction: false,
      staleReason: null,
    };
  }

  return {
    kind: 'unknown',
    retryable: false,
    requiresNewPreview: false,
    requiresProfileAction: false,
    staleReason: null,
  };
}

function buildError(
  partial: Omit<StrategyWorkflowError, 'message'> & { backendMessage: string | null },
): StrategyWorkflowError {
  const message = resolveStrategyWorkflowMessage({
    code: partial.code,
    kind: partial.kind,
    backendMessage: partial.backendMessage,
  });
  return {
    kind: partial.kind,
    code: partial.code,
    message,
    fieldErrors: partial.fieldErrors,
    retryable: partial.retryable,
    requiresNewPreview: partial.requiresNewPreview,
    requiresProfileAction: partial.requiresProfileAction,
    staleReason: partial.staleReason,
    requestId: partial.requestId,
    originalStatus: partial.originalStatus,
  };
}

/** Pure classifier — no React, no coordinator side effects. */
export function classifyStrategyWorkflowError(error: unknown): StrategyWorkflowError {
  // Profile CAS conflict thrown by saveProfile (typed Error with currentProfile).
  if (
    error &&
    typeof error === 'object' &&
    'code' in error &&
    (error as { code: unknown }).code === 'PROFILE_STALE' &&
    'currentProfile' in error
  ) {
    return buildError({
      kind: 'conflict',
      code: 'PROFILE_STALE',
      backendMessage: error instanceof Error ? error.message : null,
      fieldErrors: [],
      retryable: false,
      requiresNewPreview: false,
      requiresProfileAction: true,
      staleReason: null,
      requestId: null,
      originalStatus: 409,
    });
  }

  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') {
      return buildError({
        kind: 'retryable',
        code: WORKFLOW_ERROR_CODES.TIMEOUT,
        backendMessage: null,
        fieldErrors: [],
        retryable: true,
        requiresNewPreview: false,
        requiresProfileAction: false,
        staleReason: null,
        requestId: null,
        originalStatus: null,
      });
    }

    if (!error.response) {
      return buildError({
        kind: 'retryable',
        code: WORKFLOW_ERROR_CODES.NETWORK,
        backendMessage: null,
        fieldErrors: [],
        retryable: true,
        requiresNewPreview: false,
        requiresProfileAction: false,
        staleReason: null,
        requestId: null,
        originalStatus: null,
      });
    }

    const status = error.response.status;
    const body = error.response.data;

    if (status === 401 || status === 403) {
      return buildError({
        kind: 'authentication',
        code: status === 401 ? 'AUTH_UNAUTHORIZED' : 'AUTH_FORBIDDEN',
        backendMessage: isUnifiedError(body) ? body.message : null,
        fieldErrors: [],
        retryable: false,
        requiresNewPreview: false,
        requiresProfileAction: false,
        staleReason: null,
        requestId: isUnifiedError(body) ? body.request_id ?? null : null,
        originalStatus: status,
      });
    }

    if (status === 429) {
      return buildError({
        kind: 'rate_limited',
        code: isUnifiedError(body) ? body.code : WORKFLOW_ERROR_CODES.RATE_LIMITED,
        backendMessage: isUnifiedError(body) ? body.message : null,
        fieldErrors: [],
        retryable: true,
        requiresNewPreview: false,
        requiresProfileAction: false,
        staleReason: null,
        requestId: isUnifiedError(body) ? body.request_id ?? null : null,
        originalStatus: status,
      });
    }

    if (status === 428) {
      const code =
        isUnifiedError(body) && body.code
          ? body.code
          : 'STRATEGY_PREVIEW_VERSION_MISMATCH';
      const classified = classifyByCode(code, status);
      return buildError({
        ...classified,
        code,
        backendMessage: isUnifiedError(body) ? body.message : null,
        fieldErrors: isUnifiedError(body) ? mapFieldErrors(body.field_errors) : [],
        requestId: isUnifiedError(body) ? body.request_id ?? null : null,
        originalStatus: status,
      });
    }

    if (isUnifiedError(body)) {
      const classified = classifyByCode(body.code, status);
      if (classified.kind === 'unknown' && (status === 502 || status === 503)) {
        return buildError({
          kind: status === 503 ? 'service_unavailable' : 'retryable',
          code: body.code || (status === 503 ? 'SERVICE_UNAVAILABLE' : 'BAD_GATEWAY'),
          backendMessage: body.message,
          fieldErrors: mapFieldErrors(body.field_errors),
          retryable: true,
          requiresNewPreview: false,
          requiresProfileAction: false,
          staleReason: null,
          requestId: body.request_id ?? null,
          originalStatus: status,
        });
      }
      if (classified.kind === 'unknown' && status >= 500) {
        return buildError({
          kind: 'service_unavailable',
          code: body.code || 'INTERNAL_ERROR',
          backendMessage: body.message,
          fieldErrors: mapFieldErrors(body.field_errors),
          retryable: true,
          requiresNewPreview: false,
          requiresProfileAction: false,
          staleReason: null,
          requestId: body.request_id ?? null,
          originalStatus: status,
        });
      }
      if (classified.kind === 'unknown' && status === 404) {
        return buildError({
          kind: 'not_found',
          code: body.code,
          backendMessage: body.message,
          fieldErrors: mapFieldErrors(body.field_errors),
          retryable: false,
          requiresNewPreview: false,
          requiresProfileAction: false,
          staleReason: null,
          requestId: body.request_id ?? null,
          originalStatus: status,
        });
      }
      return buildError({
        ...classified,
        code: body.code,
        backendMessage: body.message,
        fieldErrors: mapFieldErrors(body.field_errors),
        requestId: body.request_id ?? null,
        originalStatus: status,
      });
    }

    const legacy = body as { code?: string; message?: string; detail?: unknown } | undefined;
    if (legacy?.code) {
      const classified = classifyByCode(legacy.code, status);
      return buildError({
        ...classified,
        code: legacy.code,
        backendMessage: typeof legacy.message === 'string' ? legacy.message : null,
        fieldErrors: [],
        requestId: null,
        originalStatus: status,
      });
    }

    if (status >= 500) {
      // HTTP error responses are never "offline" — only missing response is.
      return buildError({
        kind: 'service_unavailable',
        code: 'INTERNAL_ERROR',
        backendMessage: null,
        fieldErrors: [],
        retryable: true,
        requiresNewPreview: false,
        requiresProfileAction: false,
        staleReason: null,
        requestId: null,
        originalStatus: status,
      });
    }

    return buildError({
      kind: 'unknown',
      code: WORKFLOW_ERROR_CODES.UNKNOWN,
      backendMessage: error.message || null,
      fieldErrors: [],
      retryable: false,
      requiresNewPreview: false,
      requiresProfileAction: false,
      staleReason: null,
      requestId: null,
      originalStatus: status,
    });
  }

  if (error instanceof Error) {
    return buildError({
      kind: 'unknown',
      code: WORKFLOW_ERROR_CODES.UNKNOWN,
      backendMessage: error.message,
      fieldErrors: [],
      retryable: false,
      requiresNewPreview: false,
      requiresProfileAction: false,
      staleReason: null,
      requestId: null,
      originalStatus: null,
    });
  }

  return buildError({
    kind: 'unknown',
    code: WORKFLOW_ERROR_CODES.UNKNOWN,
    backendMessage: null,
    fieldErrors: [],
    retryable: false,
    requiresNewPreview: false,
    requiresProfileAction: false,
    staleReason: null,
    requestId: null,
    originalStatus: null,
  });
}

export function workflowFailure(error: unknown): { ok: false; error: StrategyWorkflowError } {
  return { ok: false, error: classifyStrategyWorkflowError(error) };
}

export function workflowSuccess<T>(data: T): { ok: true; data: T } {
  return { ok: true, data };
}
