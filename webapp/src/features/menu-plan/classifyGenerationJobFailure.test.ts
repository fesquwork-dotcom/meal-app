import { describe, expect, it } from 'vitest';

import { classifyGenerationJobFailure } from '@/features/menu-plan/classifyGenerationJobFailure';
import { getWorkflowRetryAction, getWorkflowRetryActionLabel } from '@/features/strategy-workflow/strategyWorkflowRetryAction';
import type { GenerationJob } from '@/types/api';

function job(partial: Partial<GenerationJob>): GenerationJob {
  return {
    job_id: 'job-1',
    status: 'failed',
    stage: 'failed',
    created_at: '2026-08-03T00:00:00Z',
    ...partial,
  };
}

describe('classifyGenerationJobFailure', () => {
  it('maps MENU_GENERATION_INVALID to localized copy', () => {
    const error = classifyGenerationJobFailure(
      job({
        error_code: 'MENU_GENERATION_INVALID',
        safe_message: 'Не удалось составить корректное меню. Попробуйте ещё раз.',
      }),
    );
    expect(error.code).toBe('MENU_GENERATION_INVALID');
    expect(error.message).toBe('Не удалось составить корректное меню. Попробуйте ещё раз.');
    expect(error.retryable).toBe(true);
    expect(error.message).not.toBe('Произошла неизвестная ошибка.');
  });

  it('maps GENERATION_INTERRUPTED to localized copy', () => {
    const error = classifyGenerationJobFailure(
      job({ error_code: 'GENERATION_INTERRUPTED', safe_message: 'ignored if code known' }),
    );
    expect(error.code).toBe('GENERATION_INTERRUPTED');
    expect(error.message).toBe('Генерация была прервана. Запустите её ещё раз.');
  });

  it('maps GENERATION_FAILED to generic creation failure copy', () => {
    const error = classifyGenerationJobFailure(job({ error_code: 'GENERATION_FAILED' }));
    expect(error.message).toBe('Не удалось создать меню. Попробуйте ещё раз.');
  });

  it('exposes retry CTA label Попробовать ещё раз', () => {
    const error = classifyGenerationJobFailure(job({ error_code: 'MENU_GENERATION_INVALID' }));
    const action = getWorkflowRetryAction(error);
    expect(action).toBe('retry_same_request');
    expect(getWorkflowRetryActionLabel(action, error)).toBe('Попробовать ещё раз');
  });

  it('falls back for unknown codes without showing unknown-error kind copy', () => {
    const error = classifyGenerationJobFailure(
      job({ error_code: 'SOME_NEW_CODE', safe_message: 'Не удалось создать меню. Попробуйте ещё раз.' }),
    );
    expect(error.code).toBe('GENERATION_FAILED');
    expect(error.message).toBe('Не удалось создать меню. Попробуйте ещё раз.');
  });
});
