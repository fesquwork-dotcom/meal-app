import { describe, expect, it } from 'vitest';
import { presentBasketCategories } from '@/features/basket/basketPresentation';
import {
  computeBasketSummary,
  filterBasketItems,
  formatBasketPrice,
  formatBasketSummaryLine,
  formatCategoryMeta,
  groupBasketCategories,
  hasScientificNotation,
  isApproximateWeight,
  presentAndFlattenBasket,
  resolveBasketEmptyState,
} from '@/features/basket/basketViewModel';
import type { BasketCategory } from '@/types/basket';

const sampleCategories: BasketCategory[] = [
  {
    category: 'Овощи',
    items: [
      {
        name: 'Картофель',
        weight: '≈2.75 кг',
        price: 261,
        used_in_recipes: 5,
        shopping_advice: ['Нужно купить свежим'],
        badges: ['Используется в 5 блюдах', 'Нужно купить свежим'],
      },
      {
        name: 'Сельдерей',
        weight: '3 шт + 800 г',
        price: 120,
        used_in_recipes: 1,
        shopping_advice: [],
        badges: ['Покупается один раз'],
      },
    ],
  },
  {
    category: 'Мясо',
    items: [
      {
        name: 'Куриная грудка',
        weight: '600 г',
        price: 350,
        used_in_recipes: 2,
        shopping_advice: ['Лучше купить охлаждённым'],
        badges: ['Есть в нескольких рецептах', 'Лучше купить охлаждённым'],
      },
    ],
  },
];

describe('basketViewModel formatting', () => {
  it('formats summary and prices without fractional rubles', () => {
    expect(formatBasketPrice(261)).toBe('261 ₽');
    expect(formatBasketPrice(261.0)).toBe('261 ₽');
    expect(formatBasketPrice(7920.4)).toMatch(/^7[\s\u00a0]920 ₽$/);
    expect(formatBasketSummaryLine(32, 7920)).toContain('32 позиции');
    expect(formatBasketSummaryLine(32, 7920)).toMatch(/7[\s\u00a0]920 ₽/);
    expect(formatCategoryMeta(6, 821)).toContain('6 позиций');
  });

  it('detects approximate weights and rejects scientific notation', () => {
    expect(isApproximateWeight('≈2.75 кг')).toBe(true);
    expect(isApproximateWeight('1.2 кг')).toBe(false);
    expect(hasScientificNotation('1.2E+3 г')).toBe(true);
    expect(hasScientificNotation('≈2.75 кг')).toBe(false);
    expect(hasScientificNotation('3 шт + 800 г')).toBe(false);
  });
});

describe('basketViewModel filters and progress', () => {
  const allItems = presentAndFlattenBasket(sampleCategories, () => false);

  it('builds a summary and updates progress after checks', () => {
    const unchecked = computeBasketSummary(allItems, 731);
    expect(unchecked.totalCount).toBe(3);
    expect(unchecked.checkedCount).toBe(0);
    expect(unchecked.progressPercent).toBe(0);

    const potatoId = allItems.find((item) => item.name === 'Картофель')?.id;
    expect(potatoId).toBeTruthy();
    const afterCheck = presentAndFlattenBasket(sampleCategories, (id) => id === potatoId);
    const summary = computeBasketSummary(afterCheck, 731);
    expect(summary.checkedCount).toBe(1);
    expect(summary.progressPercent).toBe(33);
  });

  it('filters by search on display name', () => {
    const found = filterBasketItems(allItems, {
      searchQuery: 'карт',
      purchaseFilter: 'all',
      hidePurchased: false,
    });
    expect(found.map((item) => item.name)).toEqual(['Картофель']);
  });

  it('filters remaining and purchased items', () => {
    const potatoId = allItems.find((item) => item.name === 'Картофель')!.id;
    const items = presentAndFlattenBasket(sampleCategories, (id) => id === potatoId);

    const remaining = filterBasketItems(items, {
      searchQuery: '',
      purchaseFilter: 'remaining',
      hidePurchased: false,
    });
    expect(remaining.map((item) => item.name).sort()).toEqual(['Куриное филе', 'Сельдерей']);

    const purchased = filterBasketItems(items, {
      searchQuery: '',
      purchaseFilter: 'purchased',
      hidePurchased: false,
    });
    expect(purchased.map((item) => item.name)).toEqual(['Картофель']);
  });

  it('hides purchased when toggle is on', () => {
    const potatoId = allItems.find((item) => item.name === 'Картофель')!.id;
    const items = presentAndFlattenBasket(sampleCategories, (id) => id === potatoId);
    const visible = filterBasketItems(items, {
      searchQuery: '',
      purchaseFilter: 'all',
      hidePurchased: true,
    });
    expect(visible.map((item) => item.name)).not.toContain('Картофель');
    expect(visible).toHaveLength(2);
  });

  it('marks fully purchased categories correctly', () => {
    const meatId = allItems.find((item) => item.categoryLabel === 'Мясо')!.id;
    const checkedMeat = presentAndFlattenBasket(sampleCategories, (id) => id === meatId);
    const groups = groupBasketCategories(checkedMeat);
    const meat = groups.find((group) => group.label === 'Мясо');
    const veggies = groups.find((group) => group.label === 'Овощи');
    expect(meat?.allPurchased).toBe(true);
    expect(veggies?.allPurchased).toBe(false);
  });

  it('resolves empty states for search, all purchased, and empty basket', () => {
    expect(
      resolveBasketEmptyState({
        totalCount: 0,
        checkedCount: 0,
        visibleCount: 0,
        searchQuery: '',
        purchaseFilter: 'all',
        hidePurchased: false,
      }),
    ).toBe('empty');

    expect(
      resolveBasketEmptyState({
        totalCount: 3,
        checkedCount: 3,
        visibleCount: 0,
        searchQuery: '',
        purchaseFilter: 'remaining',
        hidePurchased: false,
      }),
    ).toBe('all_purchased');

    expect(
      resolveBasketEmptyState({
        totalCount: 3,
        checkedCount: 1,
        visibleCount: 0,
        searchQuery: 'xyz',
        purchaseFilter: 'all',
        hidePurchased: false,
      }),
    ).toBe('search_empty');
  });
});

describe('basket presentation captions', () => {
  it('prefers special shopping advice as the single primary caption', () => {
    const presented = presentBasketCategories(sampleCategories);
    const potato = presented[0].items[0];
    expect(potato.primaryCaption).toBe('Нужно купить свежим');
    expect(potato.weight).toBe('≈2.75 кг');
    expect(potato.badges.every((badge) => badge !== potato.primaryCaption)).toBe(true);
  });

  it('keeps composite quantities as backend text', () => {
    const presented = presentBasketCategories(sampleCategories);
    expect(presented[0].items[1].weight).toBe('3 шт + 800 г');
    expect(presented[0].items[1].primaryCaption).toBe('Покупается один раз');
  });

  it('never surfaces scientific notation from presented weights', () => {
    const presented = presentBasketCategories(sampleCategories);
    for (const category of presented) {
      for (const item of category.items) {
        expect(hasScientificNotation(item.weight)).toBe(false);
      }
    }
  });
});
