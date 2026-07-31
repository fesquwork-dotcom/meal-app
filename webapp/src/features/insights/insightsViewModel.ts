import {
  buildInsightTransparencyViewModel,
  type InsightTransparencyViewModel,
} from '@/features/insights/insightTransparencyViewModel';
import type {
  InsightConfidenceLevel,
  InsightEvidenceSource,
  InsightSummary,
} from '@/types/insights';

const CONFIDENCE_LABELS: Record<InsightConfidenceLevel, string> = {
  low: 'Низкая уверенность',
  medium: 'Средняя уверенность',
  high: 'Высокая уверенность',
};

const EVIDENCE_LABELS: Record<InsightEvidenceSource, string> = {
  'trend.replacement_rate': 'история замен',
  'trend.decision_health': 'итоги решений',
  'trend.preference_stability': 'стабильность настроек',
  'trend.recommendation_effectiveness': 'эффект рекомендаций',
  'trend.positive_completion': 'подтверждённые завершения',
  'outcome.successful': 'успешные итоги',
  'delta.total_cost': 'изменения стоимости',
};

export interface InsightCardViewModel {
  id: string;
  title: string;
  summary: string;
  confidenceLabel: string;
  evidenceLabel: string;
  transparency: InsightTransparencyViewModel | null;
}

export interface InsightsViewModel {
  title: string;
  cards: InsightCardViewModel[];
}

export function buildInsightsViewModel(
  summary: InsightSummary | null | undefined,
): InsightsViewModel | null {
  if (!summary) return null;
  // Product contract: the frontend displays only confirmed insights.
  const cards = summary.insights
    .filter((insight) => insight.status === 'confirmed')
    .map((insight) => ({
      id: insight.id,
      title: insight.title,
      summary: insight.summary,
      confidenceLabel: CONFIDENCE_LABELS[insight.confidence.level],
      evidenceLabel: `Основано на данных: ${insight.evidence.sources
        .map((source) => EVIDENCE_LABELS[source])
        .join(', ')}`,
      transparency: buildInsightTransparencyViewModel(insight),
    }));
  return { title: 'Что означают ваши данные', cards };
}

