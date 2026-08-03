import { describe, expect, it } from 'vitest';

import {
  GENERATION_SUPPORTING_MESSAGE,
  resolveGenerationProgressMessage,
} from '@/features/menu-generator/useGenerationProgressMessages';

describe('resolveGenerationProgressMessage', () => {
  it('maps known stages to Russian copy', () => {
    expect(resolveGenerationProgressMessage('queued', 0)).toBe('Подготавливаем план');
    expect(resolveGenerationProgressMessage('preparing', 0)).toBe('Подготавливаем план');
    expect(resolveGenerationProgressMessage('generating', 0)).toBe('Подбираем блюда');
    expect(resolveGenerationProgressMessage('validating', 0)).toBe('Проверяем меню');
    expect(resolveGenerationProgressMessage('correcting', 0)).toBe(
      'Проверяем и улучшаем меню…',
    );
    expect(resolveGenerationProgressMessage('optimizing_budget', 0)).toBe('Оптимизируем бюджет');
    expect(resolveGenerationProgressMessage('saving', 0)).toBe('Сохраняем меню');
    expect(resolveGenerationProgressMessage('completed', 0)).toBe('Готово');
  });

  it('falls back to rotating messages when stage is absent', () => {
    expect(resolveGenerationProgressMessage(null, 0)).toBe(
      'Подбираем блюда под ваши настройки',
    );
    expect(resolveGenerationProgressMessage(undefined, 1)).toBe('Проверяем разнообразие меню');
    expect(resolveGenerationProgressMessage('unknown_stage', 2)).toBe('Собираем список покупок');
  });

  it('exposes the supporting duration hint', () => {
    expect(GENERATION_SUPPORTING_MESSAGE).toBe('Обычно это занимает несколько минут.');
  });
});
