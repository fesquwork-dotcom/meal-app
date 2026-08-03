import axios from 'axios';

import { getGenerationJob } from '@/api/generationJobs';
import type { GenerationJob, GenerationJobStatus } from '@/types/api';

export const GENERATION_JOB_POLL_INTERVAL_MS = 2500;

const TERMINAL_STATUSES: ReadonlySet<GenerationJobStatus> = new Set([
  'succeeded',
  'failed',
  'cancelled',
]);

export function isGenerationJobTerminal(status: GenerationJobStatus): boolean {
  return TERMINAL_STATUSES.has(status);
}

export function isGenerationJobInProgress(status: GenerationJobStatus): boolean {
  return status === 'queued' || status === 'running';
}

export function isAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'AbortError')
  );
}

/** Network / timeout / transient server errors — keep polling, do not fail the job. */
export function isRetryablePollError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) {
    return false;
  }
  if (error.code === 'ECONNABORTED' || !error.response) {
    return true;
  }
  const status = error.response.status;
  return status >= 500 || status === 429;
}

function createAbortError(): Error {
  if (typeof DOMException !== 'undefined') {
    return new DOMException('Aborted', 'AbortError');
  }
  const error = new Error('Aborted');
  error.name = 'AbortError';
  return error;
}

export function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(createAbortError());
      return;
    }
    const timerId = setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timerId);
      reject(createAbortError());
    };
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

export interface PollGenerationJobOptions {
  signal: AbortSignal;
  onUpdate?: (job: GenerationJob) => void;
  intervalMs?: number;
  /** Injectable for tests. Defaults to getGenerationJob. */
  fetchJob?: (jobId: string) => Promise<GenerationJob>;
}

/**
 * Polls GET /api/generation-jobs/{id} until a terminal status or abort.
 * Network errors are retried; the generation is not failed for transient poll failures.
 */
export async function pollGenerationJob(
  jobId: string,
  options: PollGenerationJobOptions,
): Promise<GenerationJob> {
  const intervalMs = options.intervalMs ?? GENERATION_JOB_POLL_INTERVAL_MS;
  const fetchJob = options.fetchJob ?? getGenerationJob;

  while (!options.signal.aborted) {
    try {
      const job = await fetchJob(jobId);
      options.onUpdate?.(job);
      if (isGenerationJobTerminal(job.status)) {
        return job;
      }
    } catch (error: unknown) {
      if (options.signal.aborted || isAbortError(error)) {
        throw createAbortError();
      }
      if (!isRetryablePollError(error)) {
        throw error;
      }
      // Transient poll failure: wait and retry without failing generation.
    }

    await delay(intervalMs, options.signal);
  }

  throw createAbortError();
}
