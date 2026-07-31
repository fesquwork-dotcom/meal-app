/**
 * Sprint 9.3 / 9.4 — presentation helpers for preference effectiveness / review.
 */

import type {
  LearnedPreference,
  LearnedPreferenceEffectiveness,
} from '@/types/learnedPreferences';

export interface LearnedPreferenceEffectivenessViewModel {
  status: LearnedPreferenceEffectiveness['status'];
  confidence: LearnedPreferenceEffectiveness['confidence'];
  generation: number;
  title: string;
  summary: string;
  evidenceText: string;
  limitationTexts: string[];
  showReview: boolean;
}

export function shouldShowEffectivenessReview(
  preference: LearnedPreference,
): boolean {
  const effectiveness = preference.effectiveness;
  if (!effectiveness) return false;
  if (preference.status !== 'active') return false;
  if (effectiveness.status !== 'ineffective') return false;
  if (effectiveness.confidence !== 'established') return false;
  const dismissed = preference.last_review_generation;
  if (dismissed == null) return true;
  return effectiveness.generation > dismissed;
}

export function buildEffectivenessViewModel(
  preference: LearnedPreference,
): LearnedPreferenceEffectivenessViewModel | null {
  const effectiveness = preference.effectiveness;
  if (!effectiveness) return null;

  return {
    status: effectiveness.status,
    confidence: effectiveness.confidence,
    generation: effectiveness.generation,
    title: effectiveness.title,
    summary: effectiveness.summary,
    evidenceText: effectiveness.evidence_text,
    limitationTexts: [...effectiveness.limitations],
    showReview: shouldShowEffectivenessReview(preference),
  };
}

export const REVIEW_TITLE = 'Стоит проверить это предпочтение';

export const REVIEW_BODY =
  'После его применения несколько планов всё ещё часто требовали замен. Вы можете оставить его включённым или отозвать.';
