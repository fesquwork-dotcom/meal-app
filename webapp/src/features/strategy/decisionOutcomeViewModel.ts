import type {
  DecisionOutcomeStatus,
  DecisionOutcomeSummary,
} from '@/types/decisionOutcome';

const STATUS_ICON: Record<DecisionOutcomeStatus, string> = {
  successful: '✓',
  neutral: '•',
  unsuccessful: '⚠',
  insufficient_data: '•',
  pending: '…',
};

export interface DecisionOutcomeItemViewModel {
  key: string;
  icon: string;
  title: string;
  label: string;
  explanation: string;
  status: DecisionOutcomeStatus;
}

export interface DecisionOutcomeViewModel {
  title: string;
  items: DecisionOutcomeItemViewModel[];
}

export function buildDecisionOutcomeViewModel(
  summary: DecisionOutcomeSummary | null | undefined,
): DecisionOutcomeViewModel | null {
  if (!summary || summary.explanations.length === 0) return null;
  return {
    title: 'Как сработали решения прошлой недели',
    items: summary.explanations.map((item) => ({
      key: item.decision_key,
      icon: STATUS_ICON[item.status],
      title: item.title,
      label: item.status_label,
      explanation: item.explanation,
      status: item.status,
    })),
  };
}
