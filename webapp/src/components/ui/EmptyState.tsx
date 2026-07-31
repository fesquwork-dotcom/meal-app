import type { FC, ReactNode } from 'react';
import { Button, Typography } from '@/components/ui';
import { cn } from '@/lib/utils';

export interface EmptyStateProps {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
  children?: ReactNode;
}

export const EmptyState: FC<EmptyStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
  className,
  children,
}) => (
  <div className={cn('flex flex-col items-center gap-4 py-8 text-center', className)}>
    <Typography variant="h3">{title}</Typography>
    {description && (
      <Typography variant="body" className="max-w-sm text-app-hint">
        {description}
      </Typography>
    )}
    {children}
    {actionLabel && onAction && (
      <Button type="button" onClick={onAction}>
        {actionLabel}
      </Button>
    )}
  </div>
);
