import { useId, type FC } from 'react';

import { Card, CardContent, Typography } from '@/components/ui';
import { buildDecisionOutcomeViewModel } from '@/features/strategy/decisionOutcomeViewModel';
import type { DecisionOutcomeSummary } from '@/types/decisionOutcome';

interface DecisionOutcomeBlockProps {
  summary: DecisionOutcomeSummary | null | undefined;
}

export const DecisionOutcomeBlock: FC<DecisionOutcomeBlockProps> = ({ summary }) => {
  const headingId = useId();
  const viewModel = buildDecisionOutcomeViewModel(summary);
  if (!viewModel) return null;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-4">
        <Typography id={headingId} variant="h3">
          {viewModel.title}
        </Typography>
        <ul aria-labelledby={headingId} className="flex flex-col gap-2">
          {viewModel.items.map((item) => (
            <li key={item.key} className="flex gap-3 rounded-app-lg bg-app-secondary p-3">
              <span aria-hidden="true" className="text-app-accent">
                {item.icon}
              </span>
              <div className="min-w-0">
                <Typography variant="label">{item.title}</Typography>
                <Typography variant="body">{item.label}</Typography>
                <Typography variant="caption" className="text-app-hint">
                  {item.explanation}
                </Typography>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
};
