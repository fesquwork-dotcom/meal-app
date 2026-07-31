/**
 * Sprint 7.3 — source-level contract for the read-only menu history UI.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

function read(relativePath: string): string {
  return readFileSync(resolve(__dirname, relativePath), 'utf-8');
}

const listPageSource = read('../../pages/MenuHistoryPage.tsx');
const detailPageSource = read('../../pages/MenuHistoryDetailPage.tsx');
const appSource = read('../../App.tsx');
const routesSource = read('../../constants/routes.ts');
const profileSource = read('../../pages/ProfilePage.tsx');
const routeMetaSource = read('../../hooks/useRouteMeta.ts');

describe('menu history routing', () => {
  it('registers list and detail routes', () => {
    expect(routesSource).toContain("HISTORY: '/history'");
    expect(appSource).toContain('<Route path={ROUTES.HISTORY} element={<MenuHistoryPage />} />');
    expect(appSource).toContain('${ROUTES.HISTORY}/:menuPlanId');
  });

  it('is reachable from the profile page', () => {
    expect(profileSource).toContain('navigate(ROUTES.HISTORY)');
    expect(profileSource).toContain('История планов');
  });

  it('resolves the header title for detail paths', () => {
    expect(routeMetaSource).toContain('isMenuHistoryDetailPath');
  });
});

describe('menu history list page', () => {
  it('uses cursor pagination with a load-more control', () => {
    expect(listPageSource).toContain('getMenuHistory(nextCursor)');
    expect(listPageSource).toContain('Показать ещё');
  });

  it('is read-only: no replacement or editing affordances', () => {
    for (const source of [listPageSource, detailPageSource]) {
      expect(source).not.toContain('replaceMeal');
      expect(source).not.toContain('ReplaceMealSheet');
      expect(source).not.toContain('generateMenu');
    }
  });

  it('explains the empty history state', () => {
    expect(listPageSource).toContain('Пока нет сохранённых планов');
  });
});

describe('menu history detail page', () => {
  it('distinguishes original and current revisions', () => {
    expect(detailPageSource).toContain('getMenuPlanOriginal');
    expect(detailPageSource).toContain('getMenuPlanDetail');
    expect(detailPageSource).toContain('has_replacements');
    expect(detailPageSource).toContain('aria-pressed');
  });

  it('labels the view as read-only', () => {
    expect(detailPageSource).toContain('только просмотр');
  });
});
