import type { FC, ReactNode } from 'react';
import { Button, Typography } from '@/components/ui';
import { cn } from '@/lib/utils';

export interface InlineErrorProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
  children?: ReactNode;
}

export const InlineError: FC<InlineErrorProps> = ({
  message,
  onRetry,
  retryLabel = 'Повторить',
  className,
  children,
}) => (
  <div
    role="alert"
    className={cn(
      'rounded-app-lg border border-app-destructive/30 bg-app-destructive/10 p-4',
      className,
    )}
  >
    <Typography variant="body" className="text-app-destructive">
      {message}
    </Typography>
    {children}
    {onRetry && (
      <Button type="button" variant="secondary" className="mt-3" onClick={onRetry}>
        {retryLabel}
      </Button>
    )}
  </div>
);
