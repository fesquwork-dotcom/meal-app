import type { DecisionExplanationChange } from '@/types/decisionExplanation';

export interface DecisionCompareViewModel {
  title: string;
  changes: DecisionExplanationChange[];
  unchanged: boolean;
}

export function buildDecisionCompareViewModel(
  changes: DecisionExplanationChange[] | null | undefined,
): DecisionCompareViewModel | null {
  if (changes == null) return null;
  return {
    title: 'Почему изменятся правила',
    changes: changes.slice(0, 8),
    unchanged: changes.length === 0,
  };
}
