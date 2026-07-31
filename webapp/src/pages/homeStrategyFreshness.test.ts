import { describe, expect, it } from 'vitest';

import {
  buildAsyncResourceViewModel,
  RESOURCE_FRESHNESS_POLICIES,
  selectResourceFreshness,
  shouldLoadResourceOnMount,
} from '@/features/async-resource';
import type { AsyncResourceState } from '@/features/async-resource';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';
import type { CurrentStrategyResponse } from '@/types/strategy';
import homePageSource from '@/pages/HomePage.tsx?raw';
import currentStrategySource from '@/hooks/useCurrentStrategy.ts?raw';

const POLICY = RESOURCE_FRESHNESS_POLICIES.currentStrategy;
const NOW = 1_700_000_000_000;

const NONE_RESPONSE: CurrentStrategyResponse = {
  status: 'none',
  strategy_id: null,
  plan_start_date: null,
  plan_end_date: null,
  strategy: null,
  explanation: null,
};

function ready(lastUpdatedAt: number): AsyncResourceState<CurrentStrategyResponse> {
  return {
    status: 'ready',
    data: NONE_RESPONSE,
    error: null,
    lastUpdatedAt,
    requestId: 1,
  };
}

describe('home current strategy freshness policy', () => {
  it('fresh cache on mount performs no GET', () => {
    const state = ready(NOW - 1_000);
    expect(selectResourceFreshness(state, POLICY, NOW)).toBe('fresh');
    expect(shouldLoadResourceOnMount(state, POLICY, NOW)).toBe(false);
  });

  it('stale cache on mount triggers background refresh', () => {
    const state = ready(NOW - POLICY.staleAfterMs - 1);
    expect(selectResourceFreshness(state, POLICY, NOW)).toBe('stale');
    expect(shouldLoadResourceOnMount(state, POLICY, NOW)).toBe(true);
  });

  it('refreshing state keeps previous data visible (MenuPlan not blocked)', () => {
    const vm = buildAsyncResourceViewModel<CurrentStrategyResponse>(
      {
        status: 'refreshing',
        data: NONE_RESPONSE,
        error: null,
        lastUpdatedAt: NOW - 10_000,
        requestId: 2,
      },
      'stale',
    );
    expect(vm.showData).toBe(true);
    expect(vm.showRefreshingIndicator).toBe(true);
    expect(vm.showInitialLoader).toBe(false);
    expect(vm.showFullError).toBe(false);
  });

  it('refresh failure preserves previous strategy data and offers retry', () => {
    const vm = buildAsyncResourceViewModel<CurrentStrategyResponse>(
      {
        status: 'error',
        data: NONE_RESPONSE,
        error: classifyStrategyWorkflowError(new Error('network')),
        lastUpdatedAt: NOW - 10_000,
        requestId: 3,
      },
      'stale',
    );
    expect(vm.showData).toBe(true);
    expect(vm.showRefreshError).toBe(true);
    expect(vm.showFullError).toBe(false);
    expect(vm.retryEnabled).toBe(true);
  });

  it('initial error without data is compact, not a hidden MenuPlan', () => {
    const vm = buildAsyncResourceViewModel<CurrentStrategyResponse>(
      {
        status: 'error',
        data: null,
        error: classifyStrategyWorkflowError(new Error('network')),
        lastUpdatedAt: null,
        requestId: 4,
      },
      'unknown',
    );
    expect(vm.showFullError).toBe(true);
    expect(vm.showData).toBe(false);
  });
});

describe('HomePage strategy wiring (source smoke)', () => {
  it('uses the shared async resource view model, no custom lifecycle', () => {
    expect(homePageSource).toContain('useCurrentStrategy');
    expect(homePageSource).toContain('buildAsyncResourceViewModel');
  });

  it('never deletes the local MenuPlan from strategy status or errors', () => {
    expect(homePageSource).not.toContain('clearMenuPlan');
    expect(homePageSource).not.toContain('setMenuPlan(null)');
  });

  it('shows a compact refresh hint instead of a blocking skeleton', () => {
    expect(homePageSource).toContain('Проверяем актуальность плана…');
    expect(homePageSource).toContain('Меню показано из сохранённой версии.');
  });

  it('emits home strategy dev observability events', () => {
    expect(homePageSource).toContain('home_strategy_refresh_started');
    expect(homePageSource).toContain('home_strategy_refresh_failed_with_menu');
    expect(homePageSource).toContain('hadMenuPlan');
  });

  it('read errors emit no coordinator event', () => {
    const strategyBlockStart = homePageSource.indexOf('useCurrentStrategy()');
    expect(strategyBlockStart).toBeGreaterThan(-1);
    expect(homePageSource).not.toContain('notifyStrategyInputsChanged');
  });

  it('current strategy hook does not touch MenuPlan storage', () => {
    expect(currentStrategySource).not.toContain('localStorage');
    expect(currentStrategySource).not.toContain('MenuPlan');
    expect(currentStrategySource).not.toContain('STORAGE_KEYS');
  });
});
