import type { FC } from 'react';
import { Typography } from '@/components/ui';
import { getDayCookingSummary } from '@/features/menu-plan/cooking/dayCookingSummary';
import type { DayMeal } from '@/types/menu';

export interface DayCookingSummaryProps {
  meals: DayMeal[];
}

export const DayCookingSummary: FC<DayCookingSummaryProps> = ({ meals }) => {
  const summary = getDayCookingSummary(meals);

  if (!summary) {
    return null;
  }

  return (
    <Typography variant="caption" className="text-app-hint" role="status">
      {summary.text}
    </Typography>
  );
};
