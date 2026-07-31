import { describe, expect, it } from 'vitest';
import axios from 'axios';

import {
  extractApiErrorCode,
  mapApiErrorToStrategyInputChangeReason,
} from '@/features/strategy-inputs/strategyInputApiErrorMapping';

function axiosError(status: number, code?: string, message = 'err') {
  return new axios.AxiosError(
    message,
    undefined,
    undefined,
    undefined,
    {
      status,
      statusText: 'Error',
      headers: {},
      config: {} as never,
      data: code ? { code, message } : { message },
    },
  );
}

describe('mapApiErrorToStrategyInputChangeReason', () => {
  it.each([
    ['STRATEGY_PREVIEW_STALE_PROFILE', 'server_stale_profile'],
    ['STRATEGY_PREVIEW_STALE_MEMORY', 'server_stale_memory'],
    ['STRATEGY_PREVIEW_STALE_BEHAVIOR', 'server_stale_behavior'],
    [
      'STRATEGY_PREVIEW_STALE_LEARNED_PREFERENCES',
      'server_stale_learned_preferences',
    ],
    ['STRATEGY_PREVIEW_STALE', 'server_stale_generic'],
    ['STRATEGY_PREVIEW_VERSION_MISMATCH', 'preview_version_mismatch'],
    ['STRATEGY_PREVIEW_EXPIRED', 'preview_token_expired'],
    ['STRATEGY_PREVIEW_INVALID', 'preview_token_invalid'],
    ['STRATEGY_PREVIEW_TOKEN_MISSING', 'preview_token_invalid'],
  ] as const)('%s → %s', (code, reason) => {
    expect(mapApiErrorToStrategyInputChangeReason(axiosError(409, code))).toBe(reason);
  });

  it('maps bare 428 to version mismatch', () => {
    expect(mapApiErrorToStrategyInputChangeReason(axiosError(428))).toBe(
      'preview_version_mismatch',
    );
    expect(extractApiErrorCode(axiosError(428))).toBe('STRATEGY_PREVIEW_VERSION_MISMATCH');
  });

  it('returns null for non-stale failures', () => {
    expect(mapApiErrorToStrategyInputChangeReason(axiosError(409, 'REQUEST_VALIDATION_ERROR'))).toBeNull();
    expect(mapApiErrorToStrategyInputChangeReason(axiosError(422, 'REQUEST_VALIDATION_ERROR'))).toBeNull();
    expect(mapApiErrorToStrategyInputChangeReason(axiosError(502))).toBeNull();
    expect(mapApiErrorToStrategyInputChangeReason(new Error('network'))).toBeNull();
  });
});
