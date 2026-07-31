import { useId, type FC } from 'react';

import { Card, CardContent, Typography } from '@/components/ui';
import { InsightTransparencyBlock } from '@/features/insights/InsightTransparencyBlock';
import type { InsightCardViewModel } from '@/features/insights/insightsViewModel';

export const InsightCard: FC<{ insight: InsightCardViewModel }> = ({ insight }) => {
  const titleId = useId();
  const summaryId = useId();
  return (
    <Card>
      <CardContent
        className="flex flex-col gap-1.5 pt-4"
        role="article"
        aria-labelledby={titleId}
        aria-describedby={summaryId}
      >
        <Typography variant="body" className="font-semibold">
          <span id={titleId}>{insight.title}</span>
        </Typography>
        <Typography variant="body" className="text-app-hint">
          <span id={summaryId}>{insight.summary}</span>
        </Typography>
        <Typography variant="caption" className="text-app-hint">
          {insight.confidenceLabel}
        </Typography>
        <Typography variant="caption" className="text-app-hint">
          {insight.evidenceLabel}
        </Typography>
        {insight.transparency ? (
          <InsightTransparencyBlock
            insightId={insight.id}
            transparency={insight.transparency}
          />
        ) : null}
      </CardContent>
    </Card>
  );
};

