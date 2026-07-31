import type { FC } from 'react';

import { Accordion, Card, CardContent, Typography } from '@/components/ui';
import {
  buildStrategyExplanationViewModel,
  parseStrategyExplanation,
} from '@/features/strategy/buildStrategyExplanationViewModel';
import { useStrategyById } from '@/hooks/useStrategyById';
import type { StrategyExplanation } from '@/types/strategy';
import { DecisionExplanationBlock } from '@/features/strategy/DecisionExplanationBlock';
import { DecisionOutcomeBlock } from '@/features/strategy/DecisionOutcomeBlock';

interface StrategyExplanationBlockProps {
  strategyId: string | null | undefined;
  /** Sprint 10.5.4 — utilization text from the generated menu (optional). */
  budgetUtilizationText?: string | null;
}

function renderReasonList(reasons: StrategyExplanation['reasons']) {
  return (
    <ul className="flex flex-col gap-2">
      {reasons.map((reason) => (
        <li key={reason.code} className="flex gap-2">
          <span aria-hidden="true" className="mt-1 text-app-accent">
            •
          </span>
          <div className="min-w-0">
            <Typography variant="label">{reason.title}</Typography>
            <Typography variant="caption" className="text-app-hint">
              {reason.description}
            </Typography>
          </div>
        </li>
      ))}
    </ul>
  );
}

export const StrategyExplanationBlock: FC<StrategyExplanationBlockProps> = ({
  strategyId,
  budgetUtilizationText,
}) => {
  const { data, isLoading, error, isRefreshError } = useStrategyById(
    strategyId,
    Boolean(strategyId),
  );

  if (!strategyId || isLoading) {
    return null;
  }

  if (error && !isRefreshError) {
    return null;
  }

  const explanation = parseStrategyExplanation(data?.explanation);
  const viewModel = buildStrategyExplanationViewModel(explanation);
  const traceDecisionExplanations =
    data?.decision_explanations?.source === 'trace' ? data.decision_explanations : null;

  if (!viewModel) {
    return null;
  }

  const utilizationReason =
    budgetUtilizationText && budgetUtilizationText.trim()
      ? {
          code: 'BUDGET_UTILIZATION',
          title: 'Использование бюджета',
          description: budgetUtilizationText.trim(),
          category: 'budget',
          priority: 0,
        }
      : null;

  const reasons = utilizationReason
    ? [utilizationReason, ...viewModel.reasons.filter((reason) => reason.code !== 'BUDGET_UTILIZATION')]
    : viewModel.reasons;

  return (
    <>
      <Card>
        <CardContent className="pt-2">
          <Accordion title="Почему план такой" defaultOpen={false}>
            <div className="flex flex-col gap-3">
              <Typography variant="h3" className="text-app-accent">
                {viewModel.headline}
              </Typography>
              <Typography variant="body" className="text-app-hint">
                {viewModel.summary}
              </Typography>
              {!traceDecisionExplanations &&
                reasons.length > 0 &&
                renderReasonList(reasons)}
              <DecisionExplanationBlock collection={traceDecisionExplanations} />
            </div>
          </Accordion>
        </CardContent>
      </Card>
      <DecisionOutcomeBlock summary={data?.decision_outcomes} />
    </>
  );
};
