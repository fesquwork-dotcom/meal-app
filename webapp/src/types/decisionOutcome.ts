export type DecisionOutcomeStatus =
  | 'pending'
  | 'successful'
  | 'neutral'
  | 'unsuccessful'
  | 'insufficient_data';

export interface OutcomeExplanation {
  decision_key: string;
  title: string;
  status: DecisionOutcomeStatus;
  status_label: string;
  explanation: string;
}

export interface DecisionOutcomeSummary {
  version: number;
  evaluated_count: number;
  successful_count: number;
  neutral_count: number;
  unsuccessful_count: number;
  insufficient_data_count: number;
  pending_count: number;
  explanations: OutcomeExplanation[];
}
