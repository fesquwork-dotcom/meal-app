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

/** Request body for POST /api/generation-jobs (Sprint 10.6). */
export interface CreateGenerationJobRequest {
  preview_token: string;
}

export type GenerationJobStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled';

export type GenerationJobStage =
  | 'queued'
  | 'preparing'
  | 'generating'
  | 'validating'
  | 'correcting'
  | 'optimizing_budget'
  | 'saving'
  | 'completed'
  | 'failed';

/** Job status from GET /api/generation-jobs/{job_id} (and active job payload). */
export interface GenerationJob {
  job_id: string;
  status: GenerationJobStatus;
  stage: GenerationJobStage;
  progress_percent?: number;
  attempt?: number;
  max_attempts?: number;
  menu_plan_id?: string;
  strategy_id?: string;
  error_code?: string;
  safe_message?: string;
  duration_ms?: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

/** 202 response from POST /api/generation-jobs. */
export interface CreateGenerationJobResponse {
  job_id: string;
  status: GenerationJobStatus;
}

/** Response from GET /api/generation-jobs/active. */
export interface ActiveGenerationJobResponse {
  job: GenerationJob | null;
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
