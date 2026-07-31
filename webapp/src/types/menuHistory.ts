/**
 * Sprint 7.3 — menu history types.
 * History is read-only: compact summaries in the list, and a durable plan
 * (current revision or immutable original snapshot) in the detail view.
 */

import type { MenuPlan } from '@/types/menu';

export type MenuPlanHistoryStatus = 'active' | 'superseded';

export type MenuPlanView = 'current' | 'original';

/** Compact list entry; never carries the full plan JSON. */
export interface MenuHistoryItem {
  menu_plan_id: string;
  plan_status: MenuPlanHistoryStatus;
  created_at: string;
  plan_start_date: string | null;
  days: number | null;
  total_cost: number | null;
  summary: string | null;
  has_replacements: boolean;
}

export interface MenuHistoryPage {
  items: MenuHistoryItem[];
  next_cursor: string | null;
}

/** Read-only detail of a durable plan in a specific view. */
export interface MenuPlanDetail {
  plan: MenuPlan;
  view: MenuPlanView;
  revision: number;
  plan_status: MenuPlanHistoryStatus;
  has_replacements: boolean;
}
