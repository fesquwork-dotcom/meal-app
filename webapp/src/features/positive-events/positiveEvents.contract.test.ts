import { describe, expect, it } from 'vitest';

import apiSource from '@/api/positiveEvents.ts?raw';
import marksComponentSource from '@/features/positive-events/MealPositiveMarks.tsx?raw';
import cardSource from '@/features/positive-events/PositiveEventCard.tsx?raw';
import hookSource from '@/features/positive-events/usePositiveEvents.ts?raw';
import dayPlanCardSource from '@/features/menu-plan/components/DayPlanCard.tsx?raw';
import weekPageSource from '@/pages/WeekPage.tsx?raw';
import homePageSource from '@/pages/HomePage.tsx?raw';
import basketPageSource from '@/pages/BasketPage.tsx?raw';
import coordinatorSource from '@/features/menu-plan/coordinateGenerationSuccess.ts?raw';

describe('positive events source contract (Sprint 6.5)', () => {
  it('sends only the allowlisted event payload to the strategy events endpoint', () => {
    expect(apiSource).toContain('/events');
    expect(apiSource).toContain('event_type');
    expect(apiSource).toContain('meal_id');
    expect(apiSource).toContain('encodeURIComponent');
    // No free-text or feedback fields travel with the event.
    expect(apiSource).not.toContain('comment');
    expect(apiSource).not.toContain('note');
  });

  it('exposes the four foundation events and nothing else', () => {
    for (const eventType of [
      "'meal_cooked'",
      "'meal_suited'",
      "'shopping_completed'",
      "'plan_completed'",
    ]) {
      expect(apiSource).toContain(eventType);
    }
    expect(apiSource).not.toContain('meal_replaced');
  });

  it('renders accessible pressable marks for meals', () => {
    expect(marksComponentSource).toContain('aria-pressed');
    expect(marksComponentSource).toContain('Приготовил');
    expect(marksComponentSource).toContain('Приготовлено');
    expect(marksComponentSource).toContain('Понравилось');
    expect(marksComponentSource).toContain('Учтём при следующих рекомендациях');
    expect(marksComponentSource).toContain('disabled');
  });

  it('renders strategy-scoped marks with a confirmation state', () => {
    expect(cardSource).toContain('role="status"');
    expect(cardSource).toContain('markedLabel');
    expect(cardSource).toContain('shopping_completed');
    expect(cardSource).toContain('plan_completed');
  });

  it('is wired into WeekPage meals and the completed-plan state', () => {
    expect(dayPlanCardSource).toContain('positiveEvents');
    expect(dayPlanCardSource).toContain('MealPositiveMarks');
    expect(weekPageSource).toContain('usePositiveEvents');
    expect(homePageSource).toContain('usePositiveEvents');
    expect(weekPageSource).toContain('plan_completed');
    expect(weekPageSource).toContain('Завершить неделю');
    expect(weekPageSource).toContain('WeekHeader');
    expect(weekPageSource).toContain('calculateMealProgress');
  });

  it('is wired into BasketPage for the shopping mark', () => {
    expect(basketPageSource).toContain('usePositiveEvents');
    expect(basketPageSource).toContain('shopping_completed');
    expect(basketPageSource).toContain('Закупка выполнена');
  });

  it('retries safely and never blocks on failures', () => {
    expect(hookSource).toContain('catch');
    expect(hookSource).toContain('pending');
    expect(hookSource).toContain('inFlightRef');
    expect(hookSource).toContain('undoPositiveEvent');
    // Backend dedupe by server-derived key makes repeats harmless.
    expect(hookSource).toContain('deduplicates');
  });

  it('clears local marks when a new menu is generated', () => {
    expect(coordinatorSource).toContain('POSITIVE_EVENT_MARKS');
  });
});
