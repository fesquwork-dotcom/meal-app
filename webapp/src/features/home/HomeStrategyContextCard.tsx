import type { FC } from 'react';

import { Button, Card, CardContent, Typography } from '@/components/ui';
import type { HomeStrategyContextViewModel } from '@/features/home/homeStrategyContextViewModel';

export interface HomeStrategyContextCardProps {
  viewModel: HomeStrategyContextViewModel;
  onOpenDetails: () => void;
}

/**
 * Optional strategy metadata block on HomePage: period, headline, lifecycle
 * status and a few applied settings. Never a source of the displayed menu —
 * the MenuPlan calendar logic stays authoritative.
 */
export const HomeStrategyContextCard: FC<HomeStrategyContextCardProps> = ({
  viewModel,
  onOpenDetails,
}) => {
  if (!viewModel.visible) {
    return null;
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-2 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          {viewModel.statusLabel && (
            <Typography
              variant="caption"
              className="inline-flex w-fit rounded-full bg-app-secondary px-3 py-1 text-app-accent"
            >
              {viewModel.statusLabel}
            </Typography>
          )}
          {viewModel.periodLabel && (
            <Typography variant="caption" className="text-app-hint">
              {viewModel.periodLabel}
            </Typography>
          )}
        </div>
        {viewModel.headline && <Typography variant="body">{viewModel.headline}</Typography>}
        {viewModel.settingsLines.length > 0 && (
          <ul className="flex flex-col gap-1">
            {viewModel.settingsLines.map((line) => (
              <li key={line}>
                <Typography variant="caption" className="text-app-hint">
                  {line}
                </Typography>
              </li>
            ))}
          </ul>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="self-start"
          onClick={onOpenDetails}
        >
          Подробнее о плане
        </Button>
      </CardContent>
    </Card>
  );
};
