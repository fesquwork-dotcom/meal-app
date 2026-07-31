import { useEffect, useState } from 'react';

const GENERATION_MESSAGES = [
  'Подбираем блюда под ваши настройки',
  'Проверяем разнообразие меню',
  'Собираем список покупок',
  'Проверяем бюджет',
] as const;

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

export function useGenerationProgressMessages(isActive: boolean): string {
  const prefersReducedMotion = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!isActive) {
      setIndex(0);
      return;
    }

    if (prefersReducedMotion) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setIndex((current) => (current + 1) % GENERATION_MESSAGES.length);
    }, 2500);

    return () => window.clearInterval(intervalId);
  }, [isActive, prefersReducedMotion]);

  return GENERATION_MESSAGES[prefersReducedMotion ? 0 : index];
}
