import type {
  DecisionExplanation,
  DecisionExplanationCollection,
} from '@/types/decisionExplanation';

export interface DecisionExplanationViewModel {
  headline: string;
  summary: string;
  source: 'trace' | 'legacy';
  visible: DecisionExplanation[];
  hiddenCount: number;
}

export function buildDecisionExplanationViewModel(
  collection: DecisionExplanationCollection | null | undefined,
  showAll = false,
): DecisionExplanationViewModel | null {
  if (!collection || collection.explanations.length === 0) return null;
  const limit = showAll ? collection.explanations.length : 4;
  return {
    headline: collection.headline,
    summary: collection.summary,
    source: collection.source,
    visible: collection.explanations.slice(0, limit),
    hiddenCount: Math.max(0, collection.explanations.length - limit),
  };
}
