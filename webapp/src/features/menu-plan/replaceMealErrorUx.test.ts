import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import { classifyStrategyWorkflowError } from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import { getWorkflowRetryAction } from '@/features/strategy-workflow/strategyWorkflowRetryAction';
import { resolveStrategyWorkflowMessage } from '@/features/strategy-workflow/strategyWorkflowErrorMessages';
import type { MenuPlan } from '@/types/menu';

function axiosErrorWithBody(status: number, data: unknown): AxiosError {
  return new AxiosError(
    'request failed',
    undefined,
    undefined,
    undefined,
    {
      data,
      status,
      statusText: 'Error',
      headers: {},
      config: { headers: new AxiosHeaders() },
    },
  );
}

const samplePlan: MenuPlan = {
  summary: 'План',
  plan_start_date: '2026-07-13',
  strategy_id: 'strategy-123',
  total_cost: 1000,
  days_plan: [
    {
      day: 'День 1',
      breakfast: '',
      lunch: '',
      dinner: 'Рыба',
      meals: [
        {
          type: 'dinner',
          recipe_name: 'Рыба',
          meal_id: 'day1_dinner',
          requires_cooking: true,
          prepared_on_day: 1,
        },
      ],
    },
  ],
  recipes: [
    {
      name: 'Рыба',
      emoji: '🐟',
      cook_time: '20 мин',
      kbju: '',
      ingredients: [{ name: 'рыба', amount: '300 г' }],
      steps: ['Готовить'],
    },
  ],
  basket: [{ category: 'Рыба', items: [{ name: 'рыба', weight: '300 г', price: 400 }] }],
};

describe('replacement error UX', () => {
  it('maps REPLACEMENT_PRICE_UNRESOLVED without offline copy', () => {
    const error = classifyStrategyWorkflowError(
      axiosErrorWithBody(422, {
        code: 'REPLACEMENT_PRICE_UNRESOLVED',
        message: 'backend text',
        request_id: 'req_replace_1',
      }),
    );
    expect(error.message).toBe(
      resolveStrategyWorkflowMessage({
        code: 'REPLACEMENT_PRICE_UNRESOLVED',
        kind: 'retryable',
        backendMessage: 'backend text',
      }),
    );
    expect(error.message).toMatch(/стоимость продуктов/);
    expect(error.message).not.toMatch(/Нет соединения/);
    expect(getWorkflowRetryAction(error)).toBe('retry_same_request');
    expect(error.requestId).toBe('req_replace_1');
  });

  it('keeps true network failures as offline', () => {
    const error = classifyStrategyWorkflowError(new AxiosError('Network Error'));
    expect(error.code).toBe('CLIENT_NETWORK_ERROR');
    expect(error.message).toMatch(/Нет соединения с сервером/);
    expect(getWorkflowRetryAction(error)).toBe('retry_same_request');
  });

  it('preserves current MenuPlan snapshot when classifying failure', () => {
    const before = structuredClone(samplePlan);
    classifyStrategyWorkflowError(
      axiosErrorWithBody(422, {
        code: 'REPLACEMENT_PRICE_UNRESOLVED',
        message: 'x',
      }),
    );
    classifyStrategyWorkflowError(
      axiosErrorWithBody(500, {
        code: 'INTERNAL_ERROR',
        message: 'y',
      }),
    );
    expect(samplePlan).toEqual(before);
    expect(samplePlan.basket[0]?.items[0]?.name).toBe('рыба');
    expect(samplePlan.days_plan[0]?.meals[0]?.recipe_name).toBe('Рыба');
  });
});
