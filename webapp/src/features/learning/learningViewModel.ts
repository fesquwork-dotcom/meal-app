import type { LearningRecommendation, RecommendedProfilePatch } from '@/types/learning';
import type { Profile } from '@/types/profile';

export interface LearningCardViewModel {
  id: string;
  title: string;
  summary: string;
  status: 'candidate' | 'accepted';
  actionLabel: string;
  dismissLabel: string;
  details: {
    reason: string;
    expectedEffect: string;
    whatWillNotChange: string;
  };
}

export function buildLearningCardViewModel(
  recommendation: LearningRecommendation,
): LearningCardViewModel {
  return {
    id: recommendation.recommendation_id,
    title: recommendation.title,
    summary: recommendation.summary,
    status: recommendation.status === 'accepted' ? 'accepted' : 'candidate',
    actionLabel: recommendation.status === 'accepted' ? 'Применить настройку' : 'Посмотреть',
    dismissLabel: 'Не сейчас',
    details: {
      reason: recommendation.reason,
      expectedEffect: recommendation.expected_effect,
      whatWillNotChange: recommendation.what_will_not_change,
    },
  };
}

/** Merge only the allowlisted Learning patch into the current server profile. */
export function applyLearningPatch(
  profile: Profile,
  patch: RecommendedProfilePatch,
): Profile {
  return {
    ...profile,
    ...(patch.cooktime ? { cooktime: patch.cooktime } : {}),
    planning_preferences: patch.planning_preferences
      ? {
          ...profile.planning_preferences,
          ...patch.planning_preferences,
        }
      : profile.planning_preferences,
    cooking_preferences: patch.cooking_preferences
      ? {
          ...profile.cooking_preferences,
          ...patch.cooking_preferences,
        }
      : profile.cooking_preferences,
  };
}
