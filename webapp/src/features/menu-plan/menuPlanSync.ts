import { getCurrentMenuPlan } from '@/api/menuPlan';
import type { MenuPlan } from '@/types/menu';

/**
 * Sprint 7.2 — reconciles the local offline cache with the durable server
 * plan. The backend is the source of truth; localStorage is only a cache.
 *
 * Returns the plan the app should adopt, or null to keep the local state.
 *
 * Rules:
 * - a legacy local plan (no menu_plan_id) is never touched or migrated;
 * - with no local plan, the server plan restores state (new device);
 * - the same durable plan with a newer server revision wins;
 * - a different durable server plan supersedes the cached one;
 * - any fetch failure keeps the local cache (offline-friendly).
 */
export async function reconcileMenuPlan(local: MenuPlan | null): Promise<MenuPlan | null> {
  if (local && !local.menu_plan_id) {
    // Legacy plan: full backward compatibility, no automatic migration.
    return null;
  }

  let server: MenuPlan | null;
  try {
    server = await getCurrentMenuPlan();
  } catch {
    return null;
  }

  if (!server || !server.menu_plan_id) {
    return null;
  }

  if (!local) {
    return server;
  }

  if (server.menu_plan_id === local.menu_plan_id) {
    const localRevision = local.menu_plan_revision ?? 0;
    const serverRevision = server.menu_plan_revision ?? 0;
    return serverRevision > localRevision ? server : null;
  }

  // A different durable plan exists on the server: it was generated later
  // (the backend keeps exactly one active plan per user).
  return server;
}
