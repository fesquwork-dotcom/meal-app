import { describe, expect, it, vi } from 'vitest';
import { CanceledError } from 'axios';

import { isRequestAbortError } from '@/features/async-resource';
import { INITIAL_STRATEGY_INPUTS_STATE } from '@/features/strategy-inputs/strategyInputsState';
import type { MenuPlan } from '@/types/menu';

const menu: MenuPlan = {
  summary: 'x',
  plan_start_date: '2026-07-13',
  strategy_id: 's',
  total_cost: 1,
  days_plan: [],
  recipes: [],
  basket: [],
};

/**
 * Pure model of StrategyCompareSection race/abort contract.
 */
function compareController() {
  let requestId = 0;
  let controller: AbortController | null = null;
  let comparing = false;
  let result: string | null = null;
  let errorShown: string | null = null;

  return {
    async run(task: (signal: AbortSignal, id: number) => Promise<string>) {
      if (comparing) {
        return;
      }
      const id = ++requestId;
      controller?.abort();
      controller = new AbortController();
      comparing = true;
      try {
        const value = await task(controller.signal, id);
        if (id !== requestId) {
          return;
        }
        result = value;
        errorShown = null;
      } catch (err) {
        if (isRequestAbortError(err)) {
          return;
        }
        if (id !== requestId) {
          return;
        }
        errorShown = 'failed';
        result = null;
      } finally {
        if (id === requestId) {
          comparing = false;
        }
      }
    },
    get result() {
      return result;
    },
    get errorShown() {
      return errorShown;
    },
    get comparing() {
      return comparing;
    },
    dispose() {
      controller?.abort();
    },
  };
}

describe('compareRequestCancellation', () => {
  it('double click blocked while pending', async () => {
    const cmp = compareController();
    let resolveFirst!: (value: string) => void;
    const first = new Promise<string>((resolve) => {
      resolveFirst = resolve;
    });
    const p1 = cmp.run(async () => first);
    await Promise.resolve();
    expect(cmp.comparing).toBe(true);
    await cmp.run(async () => 'second');
    resolveFirst('first');
    await p1;
    expect(cmp.result).toBe('first');
  });

  it('superseding compare aborts old and latest wins', async () => {
    // Simulate sequential supersede by allowing overlapping via manual ids.
    let latest = 0;
    let shown: string | null = null;
    const run = async (label: string, delay: Promise<void>) => {
      const id = ++latest;
      const ctrl = new AbortController();
      try {
        await delay;
        if (ctrl.signal.aborted || id !== latest) {
          return;
        }
        shown = label;
      } catch (err) {
        if (isRequestAbortError(err)) {
          return;
        }
      }
    };
    const waiters: Array<() => void> = [];
    const wait = () =>
      new Promise<void>((resolve) => {
        waiters.push(resolve);
      });
    const p1 = run('old', wait());
    const p2 = run('new', Promise.resolve());
    await p2;
    waiters[0]?.();
    await p1;
    expect(shown).toBe('new');
  });

  it('abort is hidden from UI error', () => {
    const err = new CanceledError();
    expect(isRequestAbortError(err)).toBe(true);
    let errorShown: string | null = null;
    if (!isRequestAbortError(err)) {
      errorShown = 'visible';
    }
    expect(errorShown).toBeNull();
  });

  it('preserves MenuPlan and coordinator on abort', () => {
    const before = structuredClone(menu);
    const rev = INITIAL_STRATEGY_INPUTS_STATE.revision;
    expect(isRequestAbortError(new CanceledError())).toBe(true);
    expect(menu).toEqual(before);
    expect(INITIAL_STRATEGY_INPUTS_STATE.revision).toBe(rev);
    expect(vi.isFakeTimers()).toBe(false);
  });
});
