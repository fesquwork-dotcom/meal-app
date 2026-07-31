/**
 * Sprint 7.2 — source-level contract for the durable MenuPlan integration:
 * the backend is the source of truth, localStorage remains an offline cache,
 * and replacements carry optimistic-concurrency identity.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

function read(relativePath: string): string {
  return readFileSync(resolve(__dirname, relativePath), 'utf-8');
}

const providerSource = read('./MenuPlanProvider.tsx');
const sheetSource = read('./ReplaceMealSheet.tsx');
const replaceMealApiSource = read('../../api/replaceMeal.ts');
const menuPlanApiSource = read('../../api/menuPlan.ts');
const syncSource = read('./menuPlanSync.ts');

describe('durable MenuPlan contract', () => {
  it('provider reconciles with the server plan once after hydration', () => {
    expect(providerSource).toContain('reconcileMenuPlan');
    expect(providerSource).toContain('persistMenuPlan(serverPlan)');
  });

  it('provider does not clobber an in-flight generation', () => {
    expect(providerSource).toContain('isGeneratingRef.current');
  });

  it('replacement sends durable identity when available', () => {
    expect(sheetSource).toContain('menu_plan_id: menuPlan.menu_plan_id');
    expect(sheetSource).toContain('expected_revision: menuPlan.menu_plan_revision');
  });

  it('replacement response adopts the new server revision', () => {
    expect(replaceMealApiSource).toContain('menu_plan_revision: data.revision');
  });

  it('current plan is read from the durable endpoint', () => {
    expect(menuPlanApiSource).toContain("'/api/menu/current'");
  });

  it('legacy local plans are never migrated automatically', () => {
    expect(syncSource).toContain('!local.menu_plan_id');
  });
});
