import { describe, expect, it } from 'vitest';
import {
  addConstraint,
  constraintsByKind,
  normalizeDietaryConstraints,
  removeConstraint,
} from '@/features/profile/dietaryConstraints';

describe('dietaryConstraints', () => {
  it('normalizes constraints with kinds', () => {
    const result = normalizeDietaryConstraints([
      { id: 'dc_1', kind: 'allergy', value: 'арахис' },
      { id: 'dc_2', kind: 'preference', value: 'рыба' },
    ]);
    expect(result).toHaveLength(2);
    expect(constraintsByKind(result, 'allergy')[0]?.value).toBe('арахис');
  });

  it('adds and removes constraints preserving kind', () => {
    const initial = normalizeDietaryConstraints([
      { id: 'dc_1', kind: 'preference', value: 'рыба' },
    ]);
    const added = addConstraint(initial, 'preference', 'сельдерей');
    expect(added).toHaveLength(2);
    const removed = removeConstraint(added, added[1].id);
    expect(removed).toHaveLength(1);
  });

  it('drops empty values', () => {
    expect(
      normalizeDietaryConstraints([{ id: 'dc_1', kind: 'allergy', value: '   ' }]),
    ).toHaveLength(0);
  });

  it('reads legacy intolerance as allergy and deduplicates safety-first', () => {
    const result = normalizeDietaryConstraints([
      { id: 'dc_1', kind: 'preference', value: 'молоко' },
      { id: 'dc_2', kind: 'intolerance', value: 'Молоко' },
    ]);
    expect(result).toEqual([{ id: 'dc_2', kind: 'allergy', value: 'Молоко' }]);
  });
});
