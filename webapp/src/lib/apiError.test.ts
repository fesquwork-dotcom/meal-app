import { describe, expect, it } from 'vitest';
import { parseApiError, profileFieldErrors } from '@/lib/apiError';
import { AxiosError, AxiosHeaders } from 'axios';

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

describe('parseApiError unified envelope', () => {
  it('uses centralized classifier message for known codes', () => {
    const message = parseApiError(
      axiosErrorWithBody(422, {
        code: 'PROFILE_PROTEIN_REQUIRED',
        message: 'backend',
        field_errors: [],
      }),
    );
    expect(message).toContain('белка');
  });

  it('maps known codes', () => {
    const message = parseApiError(
      axiosErrorWithBody(409, {
        code: 'CONFLICT_NOT_FOUND',
        message: 'Conflict not found',
      }),
    );
    expect(message).toContain('противоречие');
  });

  it('maps behavior insight not found', () => {
    const message = parseApiError(
      axiosErrorWithBody(404, {
        code: 'BEHAVIOR_INSIGHT_NOT_FOUND',
        message: 'Not found',
      }),
    );
    expect(message).toContain('больше не актуально');
  });

  it('maps behavior service unavailable', () => {
    const message = parseApiError(
      axiosErrorWithBody(503, {
        code: 'BEHAVIOR_SERVICE_UNAVAILABLE',
        message: 'Unavailable',
      }),
    );
    expect(message).toContain('наблюдения приложения');
  });

  it('extracts profile field errors', () => {
    const fields = profileFieldErrors(
      axiosErrorWithBody(422, {
        code: 'REQUEST_VALIDATION_ERROR',
        message: 'Проверьте введённые данные.',
        field_errors: [
          { field: 'profile.proteins', code: 'PROFILE_PROTEIN_REQUIRED', message: 'Выберите белок.' },
        ],
      }),
    );
    expect(fields.proteins).toBe('Выберите белок.');
  });
});
