/** Frontend API helpers for Sprint 9.5 local QA tools. */

import { api } from '@/api/client';

export type DevResetMode = 'history_only' | 'full_user';

export interface DevResetResult {
  status: string;
  mode: string;
  deleted: Record<string, number>;
}

export interface DevQaScenarioResult {
  scenario: string;
  status: string;
  anchor_date: string;
}

export interface DevDiagnosticsResult {
  dev_mode: boolean;
  version: string;
  environment: string;
  auth_mode: string;
  adaptive_preferences: boolean;
  menu_generation_configured: boolean;
  consistency: {
    status: string;
    issues: string[];
  };
  lifecycle_counts: Record<string, number>;
  scenarios: string[];
}

export async function resetCurrentDevUser(
  mode: DevResetMode,
): Promise<DevResetResult> {
  const { data } = await api.post<DevResetResult>('/api/dev/reset-current-user', {
    confirm: 'RESET',
    mode,
  });
  return data;
}

export async function loadQaScenario(
  scenario: string,
): Promise<DevQaScenarioResult> {
  const { data } = await api.post<DevQaScenarioResult>(
    '/api/dev/load-qa-scenario',
    { scenario },
  );
  return data;
}

export async function getDevDiagnostics(): Promise<DevDiagnosticsResult> {
  const { data } = await api.get<DevDiagnosticsResult>('/api/dev/diagnostics');
  return data;
}
