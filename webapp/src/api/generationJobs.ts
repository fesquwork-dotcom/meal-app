import { api } from '@/api/client';
import type {
  ActiveGenerationJobResponse,
  CreateGenerationJobRequest,
  CreateGenerationJobResponse,
  GenerationJob,
} from '@/types/api';

/** Short timeout — job endpoints are quick; generation itself is polled. */
const GENERATION_JOB_TIMEOUT_MS = 15000;

export async function createGenerationJob(
  request: CreateGenerationJobRequest,
): Promise<CreateGenerationJobResponse> {
  const { data } = await api.post<CreateGenerationJobResponse>(
    '/api/generation-jobs',
    request,
    { timeout: GENERATION_JOB_TIMEOUT_MS },
  );
  return data;
}

export async function getGenerationJob(jobId: string): Promise<GenerationJob> {
  const { data } = await api.get<GenerationJob>(
    `/api/generation-jobs/${encodeURIComponent(jobId)}`,
    { timeout: GENERATION_JOB_TIMEOUT_MS },
  );
  return data;
}

export async function getActiveGenerationJob(): Promise<GenerationJob | null> {
  const { data } = await api.get<ActiveGenerationJobResponse>('/api/generation-jobs/active', {
    timeout: GENERATION_JOB_TIMEOUT_MS,
  });
  return data.job ?? null;
}
