import { describe, expect, it } from 'vitest';

import { buildHomeStrategyContextViewModel } from '@/features/home/homeStrategyContextViewModel';
import type { AppliedSettings, CurrentStrategyResponse } from '@/types/strategy';

const NOW = new Date(2026, 6, 14); // 14 июля 2026

function response(overrides: Partial<CurrentStrategyResponse>): CurrentStrategyResponse {
  return {
    status: 'active',
    strategy_id: 'st_1',
    plan_start_date: '2026-07-13',
    plan_end_date: '2026-07-19',
    strategy: null,
    explanation: {
      version: 1,
      headline: 'Бюджетная неделя с быстрыми ужинами',
      summary: '',
      reasons: [],
    },
    applied_settings: null,
    ...overrides,
  };
}

const FULL_SETTINGS: AppliedSettings = {
  cooking: {
    cooking_time_limit: 45,
    prefer_faster_meals: true,
    preference_source: 'profile',
  },
  planning: { prefer_familiar_meals: true, familiar_meals_source: 'profile' },
  behavior: {
    applied_count: 2,
    ignored_count: 0,
    availability_preferences_applied: false,
  },
};

describe('buildHomeStrategyContextViewModel — visibility', () => {
  it('hidden without data (404 / read error keep resource empty)', () => {
    expect(buildHomeStrategyContextViewModel(null, NOW).visible).toBe(false);
    expect(buildHomeStrategyContextViewModel(undefined, NOW).visible).toBe(false);
  });

  it('hidden for status none', () => {
    const vm = buildHomeStrategyContextViewModel(
      response({ status: 'none', strategy_id: null, explanation: null }),
      NOW,
    );
    expect(vm.visible).toBe(false);
  });

  it('hidden when there is no period, headline or settings to show', () => {
    const vm = buildHomeStrategyContextViewModel(
      response({ plan_start_date: null, plan_end_date: null, explanation: null }),
      NOW,
    );
    expect(vm.visible).toBe(false);
  });

  it('visible for an active plan with metadata', () => {
    const vm = buildHomeStrategyContextViewModel(response({}), NOW);
    expect(vm.visible).toBe(true);
  });
});

describe('buildHomeStrategyContextViewModel — lifecycle status', () => {
  it('active when today is inside the plan period', () => {
    const vm = buildHomeStrategyContextViewModel(response({}), NOW);
    expect(vm.status).toBe('active');
    expect(vm.statusLabel).toBe('План активен');
  });

  it('before_start when the plan starts in the future', () => {
    const vm = buildHomeStrategyContextViewModel(
      response({ plan_start_date: '2026-07-16', plan_end_date: '2026-07-22' }),
      NOW,
    );
    expect(vm.status).toBe('before_start');
    expect(vm.statusLabel).toBe('План скоро начнётся');
  });

  it('completed when the plan period is already over', () => {
    const vm = buildHomeStrategyContextViewModel(
      response({ plan_start_date: '2026-07-01', plan_end_date: '2026-07-07' }),
      NOW,
    );
    expect(vm.status).toBe('completed');
    expect(vm.statusLabel).toBe('План завершён');
  });

  it('completed for backend status completed and superseded', () => {
    expect(buildHomeStrategyContextViewModel(response({ status: 'completed' }), NOW).status).toBe(
      'completed',
    );
    expect(buildHomeStrategyContextViewModel(response({ status: 'superseded' }), NOW).status).toBe(
      'completed',
    );
  });
});

describe('buildHomeStrategyContextViewModel — content', () => {
  it('builds a period label from both plan dates', () => {
    const vm = buildHomeStrategyContextViewModel(response({}), NOW);
    expect(vm.periodLabel).not.toBeNull();
    expect(vm.periodLabel).toContain('—');
    expect(vm.periodLabel).toContain('13');
    expect(vm.periodLabel).toContain('19');
  });

  it('omits the period when a date is missing but stays visible via headline', () => {
    const vm = buildHomeStrategyContextViewModel(response({ plan_end_date: null }), NOW);
    expect(vm.periodLabel).toBeNull();
    expect(vm.visible).toBe(true);
    expect(vm.headline).toBe('Бюджетная неделя с быстрыми ужинами');
  });

  it('normalizes an empty headline to null', () => {
    const vm = buildHomeStrategyContextViewModel(
      response({
        explanation: { version: 1, headline: '   ', summary: '', reasons: [] },
      }),
      NOW,
    );
    expect(vm.headline).toBeNull();
  });

  it('shows at most three applied settings lines', () => {
    const vm = buildHomeStrategyContextViewModel(
      response({ applied_settings: FULL_SETTINGS }),
      NOW,
    );
    expect(vm.settingsLines).toHaveLength(3);
    expect(vm.settingsLines[0]).toBe('Готовка до 45 минут');
    expect(vm.settingsLines).toContain('Приоритет более быстрых блюд');
  });

  it('skips settings lines when applied settings are absent', () => {
    const vm = buildHomeStrategyContextViewModel(response({}), NOW);
    expect(vm.settingsLines).toEqual([]);
  });

  it('never exposes strategy internals beyond display strings', () => {
    const vm = buildHomeStrategyContextViewModel(
      response({ applied_settings: FULL_SETTINGS }),
      NOW,
    );
    expect(JSON.stringify(vm)).not.toContain('st_1');
    expect(JSON.stringify(vm)).not.toContain('preference_source');
  });
});
