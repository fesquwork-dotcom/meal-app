import { useEffect, useState } from 'react';

const GENERATION_MESSAGES = [
  'Подбираем блюда под ваши настройки',
  'Проверяем разнообразие меню',
  'Собираем список покупок',
  'Проверяем бюджет',
] as const;

export const GENERATION_SUPPORTING_MESSAGE = 'Обычно это занимает несколько минут.';

const STAGE_MESSAGES: Record<string, string> = {
  queued: 'Подготавливаем план',
  preparing: 'Подготавливаем план',
  generating: 'Подбираем блюда',
  validating: 'Проверяем меню',
  correcting: 'Проверяем и улучшаем меню…',
  optimizing_budget: 'Оптимизируем бюджет',
  saving: 'Сохраняем меню',
  completed: 'Готово',
};

export interface GenerationProgressMessages {
  message: string;
  supporting: string;
}

/** Pure stage → copy mapping (also used when stage is absent → rotating fallback). */
export function resolveGenerationProgressMessage(
  stage: string | null | undefined,
  rotatingIndex: number,
): string {
  if (stage && STAGE_MESSAGES[stage]) {
    return STAGE_MESSAGES[stage];
  }
  const safeIndex =
    ((rotatingIndex % GENERATION_MESSAGES.length) + GENERATION_MESSAGES.length) %
    GENERATION_MESSAGES.length;
  return GENERATION_MESSAGES[safeIndex];
}

function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(media.matches);

    const handler = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches);
    };

    media.addEventListener('change', handler);
    return () => media.removeEventListener('change', handler);
  }, []);

  return prefersReducedMotion;
}

export function useGenerationProgressMessages(
  isActive: boolean,
  stage?: string | null,
): GenerationProgressMessages {
  const prefersReducedMotion = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!isActive) {
      setIndex(0);
      return;
    }

    if (prefersReducedMotion || stage) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setIndex((current) => (current + 1) % GENERATION_MESSAGES.length);
    }, 2500);

    return () => window.clearInterval(intervalId);
  }, [isActive, prefersReducedMotion, stage]);

  const message = resolveGenerationProgressMessage(
    stage,
    prefersReducedMotion ? 0 : index,
  );

  return {
    message,
    supporting: GENERATION_SUPPORTING_MESSAGE,
  };
}
