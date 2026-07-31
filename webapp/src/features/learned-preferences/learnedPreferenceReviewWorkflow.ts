/**
 * Sprint 9.4 — persistent keep (dismiss-review) vs existing revoke for review.
 */

import { dismissLearnedPreferenceReview } from '@/api/learnedPreferences';
import { revokePreference } from '@/features/learned-preferences/learnedPreferenceWorkflow';
import type { LearnedPreferenceActionResult } from '@/features/learned-preferences/learnedPreferenceWorkflow';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import type { WorkflowResult } from '@/features/strategy-workflow/types';
import type { LearnedPreferencesResult } from '@/types/learnedPreferences';

export type LearnedPreferenceReviewKeepSuccess = {
  action: 'keep';
  preferenceId: string;
  result: LearnedPreferencesResult;
};

export type LearnedPreferenceReviewKeepResult =
  WorkflowResult<LearnedPreferenceReviewKeepSuccess>;

export function logLearnedPreferenceReviewEvent(
  event:
    | 'learned_preference_review_shown'
    | 'learned_preference_review_kept'
    | 'learned_preference_review_revoked',
  details: {
    status?: string;
    confidence?: string;
    evidencePlans?: number;
    generation?: number;
  } = {},
): void {
  console.info(event, {
    status: details.status,
    confidence: details.confidence,
    evidence_plans: details.evidencePlans,
    generation: details.generation,
  });
}

/** Persist keep-active for the current evidence cohort. No coordinator notify. */
export async function keepLearnedPreferenceReview(
  preferenceId: string,
): Promise<LearnedPreferenceReviewKeepResult> {
  try {
    const result = await dismissLearnedPreferenceReview(preferenceId);
    logLearnedPreferenceReviewEvent('learned_preference_review_kept', {
      generation: result.preferences[0]?.effectiveness?.generation,
    });
    return { ok: true, data: { action: 'keep', preferenceId, result } };
  } catch (err: unknown) {
    return { ok: false, error: classifyStrategyWorkflowError(err) };
  }
}

export async function revokeFromLearnedPreferenceReview(
  preferenceId: string,
): Promise<LearnedPreferenceActionResult> {
  const outcome = await revokePreference(preferenceId);
  if (outcome.ok) {
    logLearnedPreferenceReviewEvent('learned_preference_review_revoked');
  }
  return outcome;
}
