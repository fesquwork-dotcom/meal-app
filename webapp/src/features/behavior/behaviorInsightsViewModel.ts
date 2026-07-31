import { getBehaviorInfluenceStatus } from '@/features/behavior/behaviorInfluence';
import type { BehaviorInsight } from '@/types/behavior';

export interface BehaviorInsightCardModel {
  id: string;
  type: BehaviorInsight['type'];
  title: string;
  description: string;
  evidenceLabel: string | null;
  statusLabel: string;
  canConfirm: boolean;
  canDismiss: boolean;
  canSnooze: boolean;
  canRevoke: boolean;
  isCandidate: boolean;
  isConfirmed: boolean;
  recommendationPrompt: string | null;
  recommendationActionLabel: string | null;
  recommendationHint: string | null;
  canApplyRecommendation: boolean;
  recommendationApplied: boolean;
  revokeConfirmTitle: string;
  revokeConfirmDescription: string;
}

export interface BehaviorInsightsViewModel {
  candidates: BehaviorInsightCardModel[];
  confirmed: BehaviorInsightCardModel[];
  candidateCount: number;
  hasCandidates: boolean;
  hasConfirmed: boolean;
  hasAny: boolean;
}

const CANDIDATE_STATUS_LABEL = 'Нужно ваше подтверждение';
const CONFIRMED_APPLIES_LABEL = 'Будет учтено при создании следующего плана';
const CONFIRMED_STORED_LABEL = 'Наблюдение подтверждено вами';
const RECOMMENDATION_PROMPT =
  'Хотите, чтобы следующие планы использовали более знакомые и предсказуемые блюда?';
const RECOMMENDATION_ACTION_LABEL = 'Использовать более знакомые блюда';
const RECOMMENDATION_HINT =
  'Настройка будет сохранена в профиле и применится только к следующим планам. Текущий план не изменится.';
const RECOMMENDATION_APPLIED_LABEL = 'Добавлено в профиль';

export const SNOOZE_DURATION_OPTIONS = [
  { value: '7_days' as const, label: 'Напомнить через 7 дней' },
  { value: '30_days' as const, label: 'Напомнить через 30 дней' },
] as const;

function confirmedStatusLabel(insight: BehaviorInsight): string {
  if (insight.status !== 'confirmed') {
    return CONFIRMED_STORED_LABEL;
  }
  return getBehaviorInfluenceStatus(insight.type) === 'applies_to_strategy'
    ? CONFIRMED_APPLIES_LABEL
    : CONFIRMED_STORED_LABEL;
}

export function buildRevokeConfirmCopy(insight: BehaviorInsight): {
  title: string;
  description: string;
} {
  if (insight.type === 'ingredient_availability_friction') {
    return {
      title: 'Больше не учитывать это наблюдение?',
      description:
        'Оно перестанет влиять на следующие планы. Текущий план не изменится.',
    };
  }
  if (insight.type === 'high_replacement_rate') {
    if (insight.recommendation?.applied) {
      return {
        title: 'Отозвать подтверждение наблюдения?',
        description:
          'Наблюдение будет отозвано. Настройка «Предпочитать знакомые блюда» останется включённой в профиле. Её можно изменить отдельно.',
      };
    }
    return {
      title: 'Отозвать подтверждение наблюдения?',
      description: 'Наблюдение и рекомендация больше не будут активны.',
    };
  }
  return {
    title: 'Отозвать подтверждение наблюдения?',
    description: 'Наблюдение больше не будет считаться подтверждённым.',
  };
}

export function formatEvidenceLabel(evidenceCount: number): string | null {
  if (!Number.isFinite(evidenceCount) || evidenceCount <= 0) {
    return null;
  }
  const count = Math.floor(evidenceCount);
  if (count === 1) {
    return 'Замечено один раз';
  }
  if (count >= 2 && count <= 4) {
    return `Замечено ${count} раза`;
  }
  return `Замечено ${count} раз`;
}

export function buildBehaviorInsightCardModel(
  insight: BehaviorInsight,
): BehaviorInsightCardModel {
  const isCandidate = insight.status === 'candidate';
  const isConfirmed = insight.status === 'confirmed';
  const recommendation = insight.recommendation ?? null;
  const canApplyRecommendation = Boolean(recommendation?.can_apply);
  const recommendationApplied = Boolean(recommendation?.applied);
  const showRecommendation =
    isConfirmed && insight.type === 'high_replacement_rate' && recommendation !== null;
  const revokeCopy = buildRevokeConfirmCopy(insight);

  return {
    id: insight.id,
    type: insight.type,
    title: insight.title,
    description: insight.description,
    evidenceLabel: formatEvidenceLabel(insight.evidence_count),
    statusLabel: isCandidate ? CANDIDATE_STATUS_LABEL : confirmedStatusLabel(insight),
    canConfirm: isCandidate && insight.can_confirm,
    canDismiss: isCandidate && insight.can_dismiss,
    canSnooze: isCandidate && insight.can_snooze,
    canRevoke: isConfirmed && insight.can_revoke,
    isCandidate,
    isConfirmed,
    recommendationPrompt:
      showRecommendation && canApplyRecommendation ? RECOMMENDATION_PROMPT : null,
    recommendationActionLabel:
      showRecommendation && canApplyRecommendation ? RECOMMENDATION_ACTION_LABEL : null,
    recommendationHint:
      showRecommendation && canApplyRecommendation ? RECOMMENDATION_HINT : null,
    canApplyRecommendation,
    recommendationApplied: showRecommendation && recommendationApplied,
    revokeConfirmTitle: revokeCopy.title,
    revokeConfirmDescription: revokeCopy.description,
  };
}

export { RECOMMENDATION_APPLIED_LABEL };

export function buildBehaviorInsightsViewModel(
  insights: BehaviorInsight[],
  candidateCount: number,
): BehaviorInsightsViewModel {
  const cards = insights.map(buildBehaviorInsightCardModel);
  const candidates = cards.filter((card) => card.isCandidate);
  const confirmed = cards.filter((card) => card.isConfirmed);
  return {
    candidates,
    confirmed,
    candidateCount,
    hasCandidates: candidates.length > 0,
    hasConfirmed: confirmed.length > 0,
    hasAny: cards.length > 0,
  };
}
