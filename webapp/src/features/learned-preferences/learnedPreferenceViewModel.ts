/**
 * Sprint 9.1 / 9.3 — pure presentation for adaptive preferences.
 * Only normalizes already-decided backend data into display strings; it never
 * computes preferences and never surfaces technical codes.
 */

import {
  buildEffectivenessViewModel,
  type LearnedPreferenceEffectivenessViewModel,
} from '@/features/learned-preferences/learnedPreferenceEffectivenessViewModel';
import { formatHistoryDate } from '@/features/menu-history/menuHistoryViewModel';
import type {
  LearnedPreference,
  LearnedPreferenceConfidence,
  LearnedPreferencesResult,
} from '@/types/learnedPreferences';

const CONFIDENCE_LABELS: Record<LearnedPreferenceConfidence, string> = {
  moderate: 'Средняя уверенность',
  strong: 'Высокая уверенность',
};

export type LearnedPreferenceCardStatus = 'candidate' | 'active';

export interface LearnedPreferenceCardViewModel {
  id: string;
  title: string;
  summary: string;
  status: LearnedPreferenceCardStatus;
  confidenceLabel: string;
  usedSinceLabel: string | null;
  planningEffectLabel: string | null;
  effectiveness: LearnedPreferenceEffectivenessViewModel | null;
}

export interface LearnedPreferencesViewModel {
  title: string;
  cards: LearnedPreferenceCardViewModel[];
}

function usedSinceLabel(preference: LearnedPreference): string | null {
  const formatted = formatHistoryDate(preference.accepted_at);
  return formatted ? `Используется системой с ${formatted}` : null;
}

function planningEffectLabel(preference: LearnedPreference): string | null {
  if (preference.status !== 'active') return null;
  if (preference.planning_effect === 'applied') {
    return usedSinceLabel(preference);
  }
  if (preference.planning_effect === 'unsupported') {
    return 'Сохранено, но пока не участвует в планировании.';
  }
  return 'Сохранено и будет доступно после включения адаптивного планирования.';
}

export function buildLearnedPreferencesViewModel(
  result: LearnedPreferencesResult | null | undefined,
): LearnedPreferencesViewModel | null {
  if (!result) return null;
  const cards = result.preferences
    // Product contract: only pending candidates and active preferences are
    // shown. Revoked/archived/transient states stay hidden.
    .filter(
      (preference) =>
        preference.status === 'candidate' || preference.status === 'active',
    )
    .map((preference) => ({
      id: preference.id,
      title: preference.title,
      summary: preference.summary,
      status: preference.status as LearnedPreferenceCardStatus,
      confidenceLabel: CONFIDENCE_LABELS[preference.confidence],
      usedSinceLabel:
        preference.status === 'active' &&
        preference.planning_effect === 'applied'
          ? usedSinceLabel(preference)
          : null,
      planningEffectLabel: planningEffectLabel(preference),
      effectiveness: buildEffectivenessViewModel(preference),
    }));
  return { title: 'Адаптивные предпочтения', cards };
}
