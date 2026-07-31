import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import { classifyStrategyWorkflowError } from '@/features/strategy-workflow/classifyStrategyWorkflowError';

function axiosErrorWithBody(status: number, data: unknown): AxiosError {
  return new AxiosError(
    'request failed',
    undefined,
    undefined,
    undefined,
    {
      status,
      data,
      headers: {},
      statusText: 'Error',
      config: { headers: new AxiosHeaders() },
    },
  );
}

describe('classifyStrategyWorkflowError', () => {
  it('classifies stale profile/memory/behavior', () => {
    for (const [code, reason] of [
      ['STRATEGY_PREVIEW_STALE_PROFILE', 'server_stale_profile'],
      ['STRATEGY_PREVIEW_STALE_MEMORY', 'server_stale_memory'],
      ['STRATEGY_PREVIEW_STALE_BEHAVIOR', 'server_stale_behavior'],
      [
        'STRATEGY_PREVIEW_STALE_LEARNED_PREFERENCES',
        'server_stale_learned_preferences',
      ],
      ['STRATEGY_PREVIEW_EXPIRED', 'preview_token_expired'],
      ['STRATEGY_PREVIEW_VERSION_MISMATCH', 'preview_version_mismatch'],
      ['STRATEGY_PREVIEW_INVALID', 'preview_token_invalid'],
      ['STRATEGY_PREVIEW_REQUIRED', 'preview_token_invalid'],
    ] as const) {
      const error = classifyStrategyWorkflowError(axiosErrorWithBody(409, { code, message: 'x' }));
      expect(error.kind).toBe('stale');
      expect(error.requiresNewPreview).toBe(true);
      expect(error.retryable).toBe(false);
      expect(error.staleReason).toBe(reason);
    }
  });

  it('classifies validation with field errors', () => {
    const error = classifyStrategyWorkflowError(
      axiosErrorWithBody(422, {
        code: 'REQUEST_VALIDATION_ERROR',
        message: 'Check fields',
        field_errors: [
          { field: 'profile.proteins', code: 'PROFILE_PROTEIN_REQUIRED', message: 'Выберите белок.' },
        ],
      }),
    );
    expect(error.kind).toBe('validation');
    expect(error.requiresProfileAction).toBe(true);
    expect(error.fieldErrors).toHaveLength(1);
    expect(error.fieldErrors[0]?.message).toContain('белок');
  });

  it('classifies 429 / 401 / 404 / 502 / 503 / network', () => {
    expect(classifyStrategyWorkflowError(axiosErrorWithBody(429, { code: 'X', message: 'slow' })).kind).toBe(
      'rate_limited',
    );
    expect(classifyStrategyWorkflowError(axiosErrorWithBody(401, { code: 'X', message: 'auth' })).kind).toBe(
      'authentication',
    );
    expect(
      classifyStrategyWorkflowError(
        axiosErrorWithBody(404, { code: 'STRATEGY_NOT_FOUND', message: 'missing' }),
      ).kind,
    ).toBe('not_found');
    expect(classifyStrategyWorkflowError(axiosErrorWithBody(502, { code: 'X', message: 'bad' })).retryable).toBe(
      true,
    );
    expect(
      classifyStrategyWorkflowError(
        axiosErrorWithBody(503, { code: 'BEHAVIOR_SERVICE_UNAVAILABLE', message: 'down' }),
      ).kind,
    ).toBe('service_unavailable');

    const network = new AxiosError('network');
    expect(classifyStrategyWorkflowError(network).code).toBe('CLIENT_NETWORK_ERROR');
    expect(classifyStrategyWorkflowError(network).retryable).toBe(true);
  });

  it('does not treat HTTP 500 domain/server errors as offline', () => {
    const withBody = classifyStrategyWorkflowError(
      axiosErrorWithBody(500, {
        code: 'INTERNAL_ERROR',
        message: 'Внутренняя ошибка сервера. Попробуйте позже.',
        request_id: 'req_test',
      }),
    );
    expect(withBody.code).toBe('INTERNAL_ERROR');
    expect(withBody.code).not.toBe('CLIENT_NETWORK_ERROR');
    expect(withBody.message).not.toMatch(/Нет соединения/);
    expect(withBody.requestId).toBe('req_test');
    expect(withBody.retryable).toBe(true);

    const bare500 = classifyStrategyWorkflowError(axiosErrorWithBody(500, { detail: 'boom' }));
    expect(bare500.code).toBe('INTERNAL_ERROR');
    expect(bare500.message).not.toMatch(/Нет соединения/);
  });

  it('maps REPLACEMENT_PRICE_UNRESOLVED to a retryable price message', () => {
    const error = classifyStrategyWorkflowError(
      axiosErrorWithBody(422, {
        code: 'REPLACEMENT_PRICE_UNRESOLVED',
        message: 'Не удалось рассчитать стоимость продуктов для этого варианта.',
        request_id: 'req_price',
        details: { unresolved_count: 7 },
      }),
    );
    expect(error.code).toBe('REPLACEMENT_PRICE_UNRESOLVED');
    expect(error.retryable).toBe(true);
    expect(error.kind).toBe('retryable');
    expect(error.message).toMatch(/стоимость продуктов/);
    expect(error.message).toMatch(/не изменён/);
    expect(error.message).not.toMatch(/Нет соединения/);
    expect(error.requestId).toBe('req_price');
  });

  it('classifies unknown errors', () => {
    const error = classifyStrategyWorkflowError(new Error('boom'));
    expect(error.kind).toBe('unknown');
    expect(error.staleReason).toBeNull();
  });
});
