/** Pure selectors for Basket UX (Sprint 10.5.3). No backend calls. */

import { buildBasketItemId } from '@/features/basket/basketUtils';
import {
  normalizeCategoryLabel,
  presentBasketCategories,
  type PresentedBasketCategory,
  type PresentedBasketItem,
} from '@/features/basket/basketPresentation';
import type { BasketCategory } from '@/types/basket';

export type BasketPurchaseFilter = 'all' | 'remaining' | 'purchased';

export interface BasketListItem {
  id: string;
  categoryIndex: number;
  itemIndex: number;
  sourceCategory: string;
  categoryLabel: string;
  name: string;
  weight: string;
  price: number;
  note?: string;
  primaryCaption?: string;
  checked: boolean;
}

export interface BasketCategoryView {
  key: string;
  categoryIndex: number;
  sourceCategory: string;
  label: string;
  itemCount: number;
  totalPrice: number;
  remainingCount: number;
  allPurchased: boolean;
  items: BasketListItem[];
}

export interface BasketSummaryView {
  totalCount: number;
  checkedCount: number;
  remainingCount: number;
  progressPercent: number;
  totalCost: number;
}

function pluralPositions(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) {
    return `${count} позиция`;
  }
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return `${count} позиции`;
  }
  return `${count} позиций`;
}

export function formatBasketPrice(value: number): string {
  const safe = Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0;
  return `${safe.toLocaleString('ru-RU')} ₽`;
}

export function formatCategoryMeta(itemCount: number, totalPrice: number): string {
  return `${pluralPositions(itemCount)} · ${formatBasketPrice(totalPrice)}`;
}

export function formatBasketSummaryLine(totalCount: number, totalCost: number): string {
  return `${pluralPositions(totalCount)} · ${formatBasketPrice(totalCost)}`;
}

export function isApproximateWeight(weight: string): boolean {
  return weight.trimStart().startsWith('≈');
}

export function hasScientificNotation(text: string): boolean {
  return /\d(?:[.,]\d+)?[eE][+-]?\d/.test(text) || text.includes('NaN') || text.includes('Infinity');
}

function matchesSearch(name: string, query: string): boolean {
  const normalizedQuery = query.trim().toLocaleLowerCase('ru-RU');
  if (!normalizedQuery) {
    return true;
  }
  return name.toLocaleLowerCase('ru-RU').includes(normalizedQuery);
}

function matchesPurchaseFilter(
  checked: boolean,
  filter: BasketPurchaseFilter,
  hidePurchased: boolean,
): boolean {
  if (filter === 'remaining') {
    return !checked;
  }
  if (filter === 'purchased') {
    return checked;
  }
  if (hidePurchased && checked) {
    return false;
  }
  return true;
}

export function buildBasketListItems(
  categories: BasketCategory[],
  presented: PresentedBasketCategory[],
  isChecked: (id: string) => boolean,
): BasketListItem[] {
  const items: BasketListItem[] = [];

  presented.forEach((category, categoryIndex) => {
    const sourceCategory = categories[categoryIndex]?.category ?? category.category;
    const label = normalizeCategoryLabel(sourceCategory);

    category.items.forEach((item, itemIndex) => {
      const sourceItem = categories[categoryIndex]?.items[itemIndex];
      const id = buildBasketItemId({
        category: sourceCategory,
        name: sourceItem?.name ?? item.name,
        weight: sourceItem?.weight ?? item.weight,
        categoryIndex,
        itemIndex,
      });

      items.push({
        id,
        categoryIndex,
        itemIndex,
        sourceCategory,
        categoryLabel: label,
        name: item.name,
        weight: item.weight,
        price: item.price,
        note: item.note,
        primaryCaption: item.primaryCaption,
        checked: isChecked(id),
      });
    });
  });

  return items;
}

export function filterBasketItems(
  items: BasketListItem[],
  options: {
    searchQuery: string;
    purchaseFilter: BasketPurchaseFilter;
    hidePurchased: boolean;
  },
): BasketListItem[] {
  return items.filter(
    (item) =>
      matchesSearch(item.name, options.searchQuery) &&
      matchesPurchaseFilter(item.checked, options.purchaseFilter, options.hidePurchased),
  );
}

export function groupBasketCategories(items: BasketListItem[]): BasketCategoryView[] {
  const groups = new Map<string, BasketCategoryView>();

  for (const item of items) {
    const key = `${item.categoryIndex}::${item.sourceCategory}`;
    let group = groups.get(key);
    if (!group) {
      group = {
        key,
        categoryIndex: item.categoryIndex,
        sourceCategory: item.sourceCategory,
        label: item.categoryLabel,
        itemCount: 0,
        totalPrice: 0,
        remainingCount: 0,
        allPurchased: true,
        items: [],
      };
      groups.set(key, group);
    }
    group.items.push(item);
    group.itemCount += 1;
    group.totalPrice += item.price;
    if (!item.checked) {
      group.remainingCount += 1;
      group.allPurchased = false;
    }
  }

  return Array.from(groups.values());
}

export function computeBasketSummary(
  items: BasketListItem[],
  totalCost: number,
): BasketSummaryView {
  const totalCount = items.length;
  const checkedCount = items.filter((item) => item.checked).length;
  const remainingCount = Math.max(totalCount - checkedCount, 0);
  const progressPercent =
    totalCount > 0 ? Math.min(Math.round((checkedCount / totalCount) * 100), 100) : 0;

  return {
    totalCount,
    checkedCount,
    remainingCount,
    progressPercent,
    totalCost,
  };
}

export function presentAndFlattenBasket(
  categories: BasketCategory[],
  isChecked: (id: string) => boolean,
): BasketListItem[] {
  const presented = presentBasketCategories(categories);
  return buildBasketListItems(categories, presented, isChecked);
}

export function resolveBasketEmptyState(input: {
  totalCount: number;
  checkedCount: number;
  visibleCount: number;
  searchQuery: string;
  purchaseFilter: BasketPurchaseFilter;
  hidePurchased: boolean;
}): 'empty' | 'all_purchased' | 'search_empty' | 'filter_empty' | null {
  if (input.totalCount === 0) {
    return 'empty';
  }
  if (input.visibleCount > 0) {
    return null;
  }
  if (input.searchQuery.trim()) {
    return 'search_empty';
  }
  if (input.purchaseFilter === 'remaining' && input.checkedCount === input.totalCount) {
    return 'all_purchased';
  }
  if (input.hidePurchased && input.checkedCount === input.totalCount) {
    return 'all_purchased';
  }
  return 'filter_empty';
}

export type { PresentedBasketItem };
