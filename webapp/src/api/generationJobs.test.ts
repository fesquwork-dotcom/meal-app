import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createGenerationJob,
  getActiveGenerationJob,
  getGenerationJob,
} from '@/api/generationJobs';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { api } from '@/api/client';

describe('generationJobs API client', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    vi.mocked(api.post).mockReset();
  });

  it('createGenerationJob posts preview_token with a short timeout', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { job_id: 'job-1', status: 'queued' },
      status: 202,
    });

    const result = await createGenerationJob({ preview_token: 'tok-1' });

    expect(result).toEqual({ job_id: 'job-1', status: 'queued' });
    expect(api.post).toHaveBeenCalledWith(
      '/api/generation-jobs',
      { preview_token: 'tok-1' },
      { timeout: 15000 },
    );
  });

  it('getGenerationJob fetches by id with a short timeout', async () => {
    const job = {
      job_id: 'job-1',
      status: 'running',
      stage: 'generating',
      created_at: '2026-08-03T00:00:00Z',
    };
    vi.mocked(api.get).mockResolvedValue({ data: job });

    const result = await getGenerationJob('job-1');

    expect(result).toEqual(job);
    expect(api.get).toHaveBeenCalledWith('/api/generation-jobs/job-1', {
      timeout: 15000,
    });
  });

  it('getGenerationJob encodes job id in the path', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        job_id: 'a/b',
        status: 'queued',
        stage: 'queued',
        created_at: '2026-08-03T00:00:00Z',
      },
    });

    await getGenerationJob('a/b');

    expect(api.get).toHaveBeenCalledWith('/api/generation-jobs/a%2Fb', {
      timeout: 15000,
    });
  });

  it('getActiveGenerationJob returns the job or null', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        job: {
          job_id: 'job-2',
          status: 'running',
          stage: 'validating',
          created_at: '2026-08-03T00:00:00Z',
        },
      },
    });

    expect(await getActiveGenerationJob()).toMatchObject({ job_id: 'job-2' });
    expect(api.get).toHaveBeenCalledWith('/api/generation-jobs/active', {
      timeout: 15000,
    });

    vi.mocked(api.get).mockResolvedValueOnce({ data: { job: null } });
    expect(await getActiveGenerationJob()).toBeNull();
  });
});
