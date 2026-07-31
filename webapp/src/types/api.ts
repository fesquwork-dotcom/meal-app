import type { ProfileApiRecord } from '@/types/profile';

export interface ApiFieldError {
  field: string;
  code: string;
  message: string;
}

/** Unified API error envelope (Sprint 5.20). */
export interface ApiErrorResponse {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
  field_errors?: ApiFieldError[];
  request_id?: string | null;
}

export interface GetProfileResponse {
  profile: ProfileApiRecord;
  legacy_constraints: string[];
  requires_constraint_review: boolean;
  revision: number;
  updated_at: string | null;
}

export interface ProfileStaleErrorBody extends ApiErrorResponse {
  code: 'PROFILE_STALE';
  details: {
    current_profile: ProfileApiRecord;
    current_revision: number;
  };
}

/** Request body for POST /api/strategy/preview (server-owned profile). */
export interface StrategyPreviewRequest {
  plan_start_date?: string;
}

/** Request body for POST /api/generate-menu (token-only). */
export interface GenerateMenuRequest {
  preview_token: string;
}

/** @deprecated Legacy FastAPI detail shape — kept for transitional fallback. */
export type ApiErrorDetail =
  | string
  | { msg: string; type?: string }[]
  | { detail?: string };

/** @deprecated Use ApiErrorResponse. */
export interface ApiErrorBody {
  detail?: ApiErrorDetail;
  code?: string;
  message?: string;
}
