import type { BasketCategory } from '@/types/basket';
import type { MenuPlan } from '@/types/menu';

export interface BasketItemIdParams {
  category: string;
  name: string;
  weight: string;
  categoryIndex: number;
  itemIndex: number;
}

function normalizeSegment(value: string): string {
  return value.trim().replace(/\s+/g, '-').toLowerCase();
}

export function buildBasketItemId(params: BasketItemIdParams): string {
  const { category, name, weight, categoryIndex, itemIndex } = params;
  const categoryPart = normalizeSegment(category) || `cat-${categoryIndex}`;
  const namePart = normalizeSegment(name) || `name-${itemIndex}`;
  const weightPart = normalizeSegment(weight) || 'no-weight';

  return `${categoryPart}::${namePart}::${weightPart}::${categoryIndex}::${itemIndex}`;
}

export function collectBasketItemIds(categories: BasketCategory[]): string[] {
  return categories.flatMap((category, categoryIndex) =>
    category.items.map((item, itemIndex) =>
      buildBasketItemId({
        category: category.category,
        name: item.name,
        weight: item.weight,
        categoryIndex,
        itemIndex,
      }),
    ),
  );
}

export function countBasketItems(categories: BasketCategory[]): number {
  return categories.reduce((sum, category) => sum + category.items.length, 0);
}

export function collectBasketItemIdsFromMenuPlan(menuPlan: MenuPlan | null): string[] {
  if (!menuPlan) {
    return [];
  }

  return collectBasketItemIds(menuPlan.basket);
}
