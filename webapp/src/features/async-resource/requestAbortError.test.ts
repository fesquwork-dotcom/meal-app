import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders, CanceledError } from 'axios';

import { isRequestAbortError } from '@/features/async-resource/requestAbortError';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';

describe('requestAbortError', () => {
  it('detects axios canceled error', () => {
    expect(isRequestAbortError(new CanceledError('canceled'))).toBe(true);
  });

  it('detects AbortError name', () => {
    const err = new Error('aborted');
    err.name = 'AbortError';
    expect(isRequestAbortError(err)).toBe(true);
  });

  it('detects ERR_CANCELED code', () => {
    const err = new AxiosError('cancel', 'ERR_CANCELED', undefined, undefined, {
      status: 0,
      data: {},
      headers: {},
      statusText: '',
      config: { headers: new AxiosHeaders() },
    });
    expect(isRequestAbortError(err)).toBe(true);
  });

  it('does not treat network failure as abort', () => {
    const err = new AxiosError('fail', undefined, undefined, undefined, {
      status: 503,
      data: { code: 'SERVICE_UNAVAILABLE' },
      headers: {},
      statusText: 'Unavailable',
      config: { headers: new AxiosHeaders() },
    });
    expect(isRequestAbortError(err)).toBe(false);
    expect(classifyStrategyWorkflowError(err).kind).toBe('service_unavailable');
  });
});
