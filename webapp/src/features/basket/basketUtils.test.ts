import { describe, expect, it } from 'vitest';
import { buildBasketItemId } from '@/features/basket/basketUtils';

describe('buildBasketItemId', () => {
  it('produces stable ids for the same input', () => {
    const params = {
      category: 'Мясо',
      name: 'Курица',
      weight: '1 кг',
      categoryIndex: 0,
      itemIndex: 0,
    };

    expect(buildBasketItemId(params)).toBe(buildBasketItemId(params));
  });

  it('does not collide for identical items at different indexes', () => {
    const first = buildBasketItemId({
      category: 'Мясо',
      name: 'Курица',
      weight: '1 кг',
      categoryIndex: 0,
      itemIndex: 0,
    });
    const second = buildBasketItemId({
      category: 'Мясо',
      name: 'Курица',
      weight: '1 кг',
      categoryIndex: 0,
      itemIndex: 1,
    });

    expect(first).not.toBe(second);
  });

  it('normalizes whitespace and case', () => {
    const lower = buildBasketItemId({
      category: '  мясо ',
      name: 'Курица',
      weight: '1 кг',
      categoryIndex: 1,
      itemIndex: 2,
    });
    const upper = buildBasketItemId({
      category: 'МЯСО',
      name: '  курица  ',
      weight: '1   кг',
      categoryIndex: 1,
      itemIndex: 2,
    });

    expect(lower).toBe(upper);
  });
});
