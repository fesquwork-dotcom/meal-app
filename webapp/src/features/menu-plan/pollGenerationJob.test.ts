import { AxiosError } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { GenerationJob } from '@/types/api';
import {
  isAbortError,
  isRetryablePollError,
  pollGenerationJob,
} from '@/features/menu-plan/pollGenerationJob';

function job(partial: Partial<GenerationJob> & Pick<GenerationJob, 'status' | 'stage'>): GenerationJob {
  return {
    job_id: 'job-1',
    created_at: '2026-08-03T00:00:00Z',
    ...partial,
  };
}

describe('pollGenerationJob', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('stops and returns on succeeded', async () => {
    const fetchJob = vi
      .fn()
      .mockResolvedValueOnce(job({ status: 'running', stage: 'generating' }))
      .mockResolvedValueOnce(job({ status: 'succeeded', stage: 'completed' }));
    const onUpdate = vi.fn();
    const abort = new AbortController();

    const pending = pollGenerationJob('job-1', {
      signal: abort.signal,
      fetchJob,
      onUpdate,
      intervalMs: 100,
    });

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchJob).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(100);
    const result = await pending;

    expect(result.status).toBe('succeeded');
    expect(fetchJob).toHaveBeenCalledTimes(2);
    expect(onUpdate).toHaveBeenCalledTimes(2);
  });

  it('stops and returns on failed', async () => {
    const fetchJob = vi.fn().mockResolvedValue(
      job({
        status: 'failed',
        stage: 'failed',
        safe_message: 'Не хватило бюджета',
      }),
    );
    const abort = new AbortController();

    const result = await pollGenerationJob('job-1', {
      signal: abort.signal,
      fetchJob,
      intervalMs: 100,
    });

    expect(result.status).toBe('failed');
    expect(result.safe_message).toBe('Не хватило бюджета');
    expect(fetchJob).toHaveBeenCalledTimes(1);
  });

  it('retries network errors without failing', async () => {
    const networkError = new AxiosError('Network Error');
    const fetchJob = vi
      .fn()
      .mockRejectedValueOnce(networkError)
      .mockResolvedValueOnce(job({ status: 'succeeded', stage: 'completed' }));
    const abort = new AbortController();

    const pending = pollGenerationJob('job-1', {
      signal: abort.signal,
      fetchJob,
      intervalMs: 50,
    });

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchJob).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(50);
    const result = await pending;

    expect(result.status).toBe('succeeded');
    expect(fetchJob).toHaveBeenCalledTimes(2);
  });

  it('stops polling when aborted (unmount)', async () => {
    const fetchJob = vi.fn().mockResolvedValue(job({ status: 'running', stage: 'generating' }));
    const abort = new AbortController();

    const pending = pollGenerationJob('job-1', {
      signal: abort.signal,
      fetchJob,
      intervalMs: 1000,
    });

    await vi.advanceTimersByTimeAsync(0);
    abort.abort();

    await expect(pending).rejects.toSatisfy((error: unknown) => isAbortError(error));
  });
});

describe('isRetryablePollError', () => {
  it('treats network and timeout errors as retryable', () => {
    expect(isRetryablePollError(new AxiosError('Network Error'))).toBe(true);

    const timeout = new AxiosError('timeout');
    timeout.code = 'ECONNABORTED';
    expect(isRetryablePollError(timeout)).toBe(true);
  });

  it('does not retry permanent client errors', () => {
    const err = new AxiosError('Not found');
    err.response = {
      status: 404,
      data: {},
      statusText: 'Not Found',
      headers: {},
      config: { headers: {} as never },
    };
    expect(isRetryablePollError(err)).toBe(false);
  });
});
