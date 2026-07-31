import type { FC } from 'react';
import { Typography } from '@/components/ui';
import { cn } from '@/lib/utils';
import type { CookingStatus } from '@/features/menu-plan/cooking/types';

export interface CookingStatusBadgeProps {
  status: CookingStatus;
  className?: string;
}

const KIND_STYLES: Record<Exclude<CookingStatus['kind'], 'unknown'>, string> = {
  cook: 'bg-app-button/15 text-app-accent',
  leftover: 'bg-app-secondary text-app-text',
  prepared: 'bg-app-secondary text-app-hint',
  ready: 'bg-app-bg text-app-hint',
};

export const CookingStatusBadge: FC<CookingStatusBadgeProps> = ({ status, className }) => {
  if (status.kind === 'unknown' || !status.label) {
    return null;
  }

  return (
    <div className={cn('mt-1 flex flex-col gap-0.5', className)}>
      <span
        className={cn(
          'inline-flex w-fit max-w-full rounded-full px-2 py-0.5 text-xs font-medium',
          KIND_STYLES[status.kind],
        )}
        aria-label={`Статус готовки: ${status.label}`}
      >
        {status.label}
      </span>
      {status.kind === 'leftover' && status.sourceLabel && (
        <Typography variant="caption" className="break-words text-app-hint">
          {status.sourceLabel}
        </Typography>
      )}
    </div>
  );
};
