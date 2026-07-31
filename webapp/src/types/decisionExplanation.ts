export type DecisionExplanationSource = 'trace' | 'legacy';
export type DecisionExplanationChangeType =
  | 'value_changed'
  | 'source_changed'
  | 'rule_changed';

export interface DecisionExplanation {
  version: number;
  decision_key: string;
  title: string;
  outcome: string;
  explanation: string;
  source_label: string | null;
  supporting_points: string[];
  alternative_note: string | null;
  confidence_label: string | null;
}

export interface DecisionExplanationCollection {
  version: number;
  headline: string;
  summary: string;
  explanations: DecisionExplanation[];
  source: DecisionExplanationSource;
}

export interface DecisionExplanationChange {
  decision_key: string;
  title: string;
  before: string;
  after: string;
  explanation: string;
  change_type: DecisionExplanationChangeType;
}
