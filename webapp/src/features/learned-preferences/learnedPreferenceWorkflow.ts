/**
 * Sprint 9.1 — typed accept/revoke workflow for adaptive preferences.
 * Pure orchestration: executes an API action and classifies any error into the
 * shared WorkflowResult contract. No React, no state.
 */

import {
  acceptLearnedPreference,
  revokeLearnedPreference,
} from '@/api/learnedPreferences';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import type { WorkflowResult } from '@/features/strategy-workflow/types';
import type { LearnedPreferencesResult } from '@/types/learnedPreferences';

export type LearnedPreferenceActionType = 'accept' | 'revoke';

export interface LearnedPreferenceActionSuccess {
  action: LearnedPreferenceActionType;
  preferenceId: string;
  result: LearnedPreferencesResult;
}

export type LearnedPreferenceActionResult =
  WorkflowResult<LearnedPreferenceActionSuccess>;

export type LearnedPreferenceExecutor = (
  preferenceId: string,
) => Promise<LearnedPreferencesResult>;

export async function runLearnedPreferenceAction(
  action: LearnedPreferenceActionType,
  preferenceId: string,
  execute: LearnedPreferenceExecutor,
): Promise<LearnedPreferenceActionResult> {
  try {
    const result = await execute(preferenceId);
    return { ok: true, data: { action, preferenceId, result } };
  } catch (err: unknown) {
    return { ok: false, error: classifyStrategyWorkflowError(err) };
  }
}

export function acceptPreference(
  preferenceId: string,
): Promise<LearnedPreferenceActionResult> {
  return runLearnedPreferenceAction('accept', preferenceId, acceptLearnedPreference);
}

export function revokePreference(
  preferenceId: string,
): Promise<LearnedPreferenceActionResult> {
  return runLearnedPreferenceAction('revoke', preferenceId, revokeLearnedPreference);
}
