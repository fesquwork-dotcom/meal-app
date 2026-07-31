import { describe, expect, it } from 'vitest';

import {
  buildMemorySignalViewModel,
  buildMemorySignalsViewModel,
  parseMemorySignals,
} from '@/features/memory/memorySignalsViewModel';
import type { MemorySignal } from '@/types/memory';

function signal(overrides: Partial<MemorySignal> = {}): MemorySignal {
  return {
    id: 'sig-1',
    type: 'avoid_ingredient',
    label: 'Гречка',
    status: 'observed',
    evidence_count: 2,
    confidence: 0.6,
    ...overrides,
  };
}

describe('parseMemorySignals', () => {
  it('parses a valid signals response', () => {
    const parsed = parseMemorySignals({ signals: [signal()] });
    expect(parsed).toHaveLength(1);
    expect(parsed[0].type).toBe('avoid_ingredient');
  });

  it('returns empty list for malformed or missing payloads', () => {
    expect(parseMemorySignals(null)).toEqual([]);
    expect(parseMemorySignals({})).toEqual([]);
    expect(parseMemorySignals({ signals: 'nope' })).toEqual([]);
    expect(parseMemorySignals({ signals: [{ id: 'x' }] })).toEqual([]);
  });
});

describe('avoid ingredient wording', () => {
  it('uses tentative wording for observed signals', () => {
    const vm = buildMemorySignalViewModel(signal({ status: 'observed' }));
    expect(vm.title).toBe('Возможно, вам не подходит Гречка');
    expect(vm.detail).toContain('Подтвердите, чтобы учитывать в будущих планах');
    expect(vm.isConfirmed).toBe(false);
    // Never leak raw codes or percentages.
    expect(vm.title).not.toContain('avoid_ingredient');
    expect(vm.title).not.toContain('%');
  });

  it('uses assertive wording for confirmed signals', () => {
    const vm = buildMemorySignalViewModel(signal({ status: 'confirmed', confidence: 1 }));
    expect(vm.title).toBe('Не предлагать Гречка');
    expect(vm.isConfirmed).toBe(true);
    expect(vm.canPromote).toBe(true);
    expect(vm.promotionHint).toContain('постоянно исключаться');
    expect(vm.detail).toContain('Запомнено по вашим заменам');
  });
});

describe('prefer faster wording', () => {
  it('observed vs confirmed', () => {
    const observed = buildMemorySignalViewModel(
      signal({ type: 'prefer_faster_meals', label: 'Более быстрые блюда', status: 'observed' }),
    );
    expect(observed.title).toBe('Вы несколько раз выбирали более быстрые блюда');

    const confirmed = buildMemorySignalViewModel(
      signal({ type: 'prefer_faster_meals', status: 'confirmed', confidence: 1 }),
    );
    expect(confirmed.title).toBe('Предпочитать более быстрые блюда');
    expect(confirmed.canPromote).toBe(true);
    expect(confirmed.detail).toContain('Запомнено по вашим заменам');
  });
});

describe('promotion eligibility', () => {
  it('allows promotion for confirmed avoid and faster signals', () => {
    const confirmedAvoid = buildMemorySignalViewModel(
      signal({ type: 'avoid_ingredient', status: 'confirmed' }),
    );
    expect(confirmedAvoid.canPromote).toBe(true);

    const observedAvoid = buildMemorySignalViewModel(
      signal({ type: 'avoid_ingredient', status: 'observed' }),
    );
    expect(observedAvoid.canPromote).toBe(false);

    const faster = buildMemorySignalViewModel(
      signal({ type: 'prefer_faster_meals', status: 'confirmed' }),
    );
    expect(faster.canPromote).toBe(true);
  });
});

describe('buildMemorySignalsViewModel', () => {
  it('drops dismissed signals', () => {
    const vms = buildMemorySignalsViewModel([
      signal({ id: 'a', status: 'observed' }),
      signal({ id: 'b', status: 'dismissed' }),
    ]);
    expect(vms.map((v) => v.id)).toEqual(['a']);
  });
});
