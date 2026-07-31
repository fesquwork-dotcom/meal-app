import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const basketSource = readFileSync(resolve(__dirname, './Basket.tsx'), 'utf-8');
const pageSource = readFileSync(resolve(__dirname, '../../pages/BasketPage.tsx'), 'utf-8');
const layoutSource = readFileSync(resolve(__dirname, '../../layouts/RootLayout.tsx'), 'utf-8');

describe('Basket UX contract (Sprint 10.5.3)', () => {
  it('renders a compact summary with progress bar', () => {
    expect(basketSource).toContain('basket-summary');
    expect(basketSource).toContain('formatBasketSummaryLine');
    expect(basketSource).toContain('role="progressbar"');
    expect(basketSource).toContain('Куплено {summary.checkedCount} из {summary.totalCount}');
  });

  it('supports local search and purchase filters without backend calls', () => {
    expect(basketSource).toContain('Поиск продукта');
    expect(basketSource).toContain('filterBasketItems');
    expect(basketSource).toContain("label: 'Все'");
    expect(basketSource).toContain("label: 'Не куплено'");
    expect(basketSource).toContain("label: 'Куплено'");
    expect(basketSource).toContain('Скрыть купленные');
    expect(basketSource).not.toContain('fetch(');
    expect(basketSource).not.toContain('axios');
  });

  it('keeps weight as ready-made text and highlights approximate values', () => {
    expect(basketSource).toContain('isApproximateWeight');
    expect(basketSource).toContain('{weight}');
    expect(basketSource).not.toContain('parseWeight');
    expect(basketSource).not.toContain('Number(weight');
  });

  it('uses collapsible categories with aria-expanded', () => {
    expect(basketSource).toContain('aria-expanded={!collapsed}');
    expect(basketSource).toContain('formatCategoryMeta');
    expect(basketSource).toContain('allPurchased');
  });

  it('keeps checkbox labels and 44px touch targets', () => {
    expect(basketSource).toContain('aria-label={`Куплено: ${name}`}');
    expect(basketSource).toContain('min-h-11');
  });

  it('wires empty and loading copy on BasketPage', () => {
    expect(pageSource).toContain('Собираем список покупок…');
    expect(pageSource).toContain('В корзине пока нет продуктов');
  });

  it('keeps bottom navigation clearance on the app shell', () => {
    expect(layoutSource).toContain('pb-32');
    expect(layoutSource).toContain('BottomNavigation');
  });

  it('does not change Basket Engine or wire-format parsing', () => {
    expect(basketSource).not.toContain('canonical_name');
    expect(basketSource).not.toContain('CanonicalUnitPolicy');
    expect(basketSource).not.toContain('mergeQuantities');
  });
});
