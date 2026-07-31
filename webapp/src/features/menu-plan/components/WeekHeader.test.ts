import { describe, expect, it } from 'vitest';

import weekHeaderSource from '@/features/menu-plan/components/WeekHeader.tsx?raw';

describe('WeekHeader source contract', () => {
  it('is a single compact card with cost, progress, stats and settings link', () => {
    expect(weekHeaderSource).toContain('data-testid="week-header"');
    expect(weekHeaderSource).toContain('formatCurrency(totalCost)');
    expect(weekHeaderSource).toContain('приготовлено');
    expect(weekHeaderSource).toContain('role="progressbar"');
    expect(weekHeaderSource).toContain('в корзине');
    expect(weekHeaderSource).toContain('Изменили настройки?');
    expect(weekHeaderSource).toContain('Посмотреть, как изменится следующий план');
    expect(weekHeaderSource).toContain('onOpenSettings');
    expect(weekHeaderSource.match(/<Card[\s>]/g)?.length).toBe(1);
    expect(weekHeaderSource).not.toContain('grid-cols-3');
  });

  it('clamps long summary and only offers expand when needed', () => {
    expect(weekHeaderSource).toContain('line-clamp-4');
    expect(weekHeaderSource).toContain('Показать полностью');
    expect(weekHeaderSource).toContain('Свернуть');
    expect(weekHeaderSource).toContain('scrollHeight');
    expect(weekHeaderSource).toContain('canExpand');
  });

  it('adapts cost/progress row without nested cards', () => {
    expect(weekHeaderSource).toContain('sm:flex-row');
    expect(weekHeaderSource).toContain('Неделя завершена');
    expect(weekHeaderSource).not.toContain('WeekMealProgress');
  });

  it('keeps touch-friendly settings control', () => {
    expect(weekHeaderSource).toContain('min-h-11');
  });
});
