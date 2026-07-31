import { describe, expect, it } from 'vitest';
import {
  formatCalories,
  formatCookTime,
  glossaryNote,
  groupIngredients,
  normalizeSubstitutes,
  normalizeTips,
  resolveDisplayName,
} from '@/features/recipes/ingredientPresentation';
import {
  formatCategoryTitle,
  guessCategory,
  presentBasketCategories,
  resolveBasketDisplayName,
} from '@/features/basket/basketPresentation';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';

describe('ingredient presentation', () => {
  it('uses common grocery names instead of technical wording', () => {
    expect(resolveDisplayName('томат')).toBe('Помидоры');
    expect(resolveDisplayName('куриная грудка')).toBe('Куриное филе');
  });

  it('adds glossary notes for rare ingredients only', () => {
    expect(glossaryNote('Тахини')).toBe('кунжутная паста');
    expect(glossaryNote('Булгур')).toBe('пшеничная крупа');
    expect(glossaryNote('Рис')).toBeUndefined();
  });

  it('groups ingredients and marks pantry staples', () => {
    const groups = groupIngredients([
      { name: 'Куриное филе', amount: '600 г' },
      { name: 'Паприка', amount: '5 г' },
      { name: 'Тахини', amount: '20 г' },
      { name: 'Соль', amount: 'по вкусу', contribution: 'pantry' },
    ]);

    expect(groups.map((group) => group.id)).toEqual(['main', 'spices', 'sauces', 'pantry']);
    const pantry = groups.find((group) => group.id === 'pantry');
    expect(pantry?.items[0]?.pantryLabel).toBe('Есть дома');
    expect(groups.find((group) => group.id === 'sauces')?.items[0]?.note).toBe('кунжутная паста');
  });

  it('hides empty tips and normalizes substitutes', () => {
    expect(normalizeTips(undefined)).toEqual([]);
    expect(normalizeTips('Оставьте под крышкой')).toEqual(['Оставьте под крышкой']);
    expect(normalizeSubstitutes([{ from: 'Авокадо', to: 'Огурец' }])).toEqual([
      { original: 'Авокадо', replacement: 'Огурцы' },
    ]);
  });

  it('formats meta fields', () => {
    expect(formatCookTime('25')).toBe('25 минут');
    expect(formatCookTime('25 мин')).toBe('25 мин');
    expect(formatCalories('540')).toBe('540 ккал');
  });
});

describe('basket presentation', () => {
  it('never shows underscore canonical keys', () => {
    expect(resolveBasketDisplayName('chicken_breast')).toBe('Chicken breast');
    expect(resolveBasketDisplayName('томат')).toBe('Помидоры');
  });

  it('formats category titles and sends unknowns to Прочее', () => {
    expect(formatCategoryTitle('Мясо')).toContain('Мясо');
    expect(formatCategoryTitle('Молочное')).toContain('Молочные продукты');
    expect(guessCategory('Неизвестный xyz')).toBe('Прочее');
  });

  it('presents badges and hides empty advice', () => {
    const presented = presentBasketCategories([
      {
        category: 'Мясо',
        items: [
          {
            name: 'Куриная грудка',
            weight: '600 г',
            price: 350,
            used_in_recipes: 3,
            shopping_advice: ['Лучше купить охлаждённым'],
            badges: ['Используется в 3 блюдах', 'Лучше купить охлаждённым'],
          },
        ],
      },
      {
        category: 'Продукты',
        items: [{ name: 'Экзот', weight: '1 шт', price: 10 }],
      },
    ]);

    expect(presented[0].title).toContain('Мясо');
    expect(presented[0].items[0].name).toBe('Куриное филе');
    expect(presented[0].items[0].primaryCaption).toBe('Лучше купить охлаждённым');
    expect(presented[0].items[0].badges).not.toContain('Лучше купить охлаждённым');
    expect(presented[1].title).toContain('Прочее');
    expect(presented[1].items[0].shoppingAdvice).toEqual([]);
  });
});

describe('normalizeMenuPlan cooking experience fields', () => {
  it('preserves tips, substitutes, and basket enrichment', () => {
    const plan = normalizeMenuPlan({
      summary: 'План',
      total_cost: 1000,
      days_plan: [{ day: 'День 1', meals: [{ type: 'dinner', recipe_name: 'Плов' }] }],
      recipes: [
        {
          name: 'Плов',
          ingredients: [
            { name: 'Рис', amount: '300 г' },
            { name: 'Соль', amount: 'по вкусу', contribution: 'pantry' },
          ],
          steps: ['Варить'],
          tips: ['Оставьте под крышкой'],
          substitutes: [{ original: 'Авокадо', replacement: 'Огурец' }],
          calories_per_portion: '540 ккал',
        },
      ],
      basket: [
        {
          category: 'Крупы',
          items: [
            {
              name: 'Рис',
              weight: '300 г',
              price: 80,
              used_in_recipes: 2,
              shopping_advice: ['Можно взять большую упаковку'],
              badges: ['Есть в нескольких рецептах'],
            },
          ],
        },
      ],
    });

    expect(plan?.recipes[0].tips).toEqual(['Оставьте под крышкой']);
    expect(plan?.recipes[0].substitutes?.[0].replacement).toBe('Огурцы');
    expect(plan?.basket[0].items[0].used_in_recipes).toBe(2);
    expect(plan?.basket[0].items[0].shopping_advice).toContain('Можно взять большую упаковку');
  });
});
