import type { FC } from 'react';
import { Button, Typography } from '@/components/ui';
import {
  getWorkflowRetryAction,
  getWorkflowRetryActionLabel,
} from '@/features/strategy-workflow/strategyWorkflowRetryAction';
import type { StrategyWorkflowError, WorkflowRetryAction } from '@/features/strategy-workflow/types';
import { cn } from '@/lib/utils';

export type StrategyWorkflowErrorPanelVariant = 'full' | 'compact' | 'inline';

export interface StrategyWorkflowErrorPanelProps {
  error: StrategyWorkflowError;
  /** @deprecated Prefer `variant`. */
  compact?: boolean;
  variant?: StrategyWorkflowErrorPanelVariant;
  onAction?: (action: WorkflowRetryAction) => void;
  onRetry?: () => void;
  onOpenProfile?: () => void;
  onReloadProfile?: () => void;
  onRestart?: () => void;
  onDismiss?: () => void;
  className?: string;
  showRequestId?: boolean;
}

function resolveVariant(
  variant: StrategyWorkflowErrorPanelVariant | undefined,
  compact: boolean | undefined,
): StrategyWorkflowErrorPanelVariant {
  if (variant) {
    return variant;
  }
  return compact ? 'compact' : 'full';
}

export const StrategyWorkflowErrorPanel: FC<StrategyWorkflowErrorPanelProps> = ({
  error,
  compact = false,
  variant,
  onAction,
  onRetry,
  onOpenProfile,
  onReloadProfile,
  onRestart,
  onDismiss,
  className,
  showRequestId = false,
}) => {
  const resolvedVariant = resolveVariant(variant, compact);
  const action = getWorkflowRetryAction(error);
  const label = getWorkflowRetryActionLabel(action);
  const isInline = resolvedVariant === 'inline';
  const isCompact = resolvedVariant === 'compact' || isInline;

  const handleAction = (next: WorkflowRetryAction) => {
    if (import.meta.env.DEV) {
      console.info('strategy_workflow_retry_requested', {
        kind: error.kind,
        code: error.code,
        retry_action: next,
        http_status: error.originalStatus,
      });
    }
    if (onAction) {
      onAction(next);
      return;
    }
    if (next === 'retry_same_request' || next === 'build_new_preview') {
      onRetry?.();
      return;
    }
    if (next === 'open_profile') {
      onOpenProfile?.();
      return;
    }
    if (next === 'reload_profile') {
      onReloadProfile?.();
      return;
    }
    if (next === 'restart_app') {
      onRestart?.();
    }
  };

  const canInvoke =
    Boolean(onAction) ||
    ((action === 'retry_same_request' || action === 'build_new_preview') && Boolean(onRetry)) ||
    (action === 'open_profile' && Boolean(onOpenProfile)) ||
    (action === 'reload_profile' && Boolean(onReloadProfile)) ||
    (action === 'restart_app' && Boolean(onRestart));

  return (
    <div
      role="alert"
      className={cn(
        resolvedVariant === 'full'
          ? 'rounded-app-lg border border-app-destructive/30 bg-app-destructive/10 p-4'
          : 'flex flex-col gap-2',
        className,
      )}
    >
      <Typography
        variant={isCompact ? 'caption' : 'body'}
        className="text-app-destructive"
      >
        {error.message}
      </Typography>

      {error.fieldErrors.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {error.fieldErrors.map((fieldError) => (
            <li key={`${fieldError.field}:${fieldError.code}`}>
              <Typography variant="caption" className="text-app-destructive">
                {fieldError.message}
              </Typography>
            </li>
          ))}
        </ul>
      )}

      {showRequestId && error.requestId && (
        <Typography variant="caption" className="mt-2 text-app-hint">
          Код обращения: {error.requestId}
        </Typography>
      )}

      {!isInline && (
        <div className={cn('flex flex-wrap gap-2', isCompact ? 'mt-1' : 'mt-3')}>
          {label && canInvoke && (
            <Button
              type="button"
              variant="secondary"
              size={isCompact ? 'sm' : 'md'}
              onClick={() => handleAction(action)}
            >
              {label}
            </Button>
          )}
          {onDismiss && (
            <Button
              type="button"
              variant="ghost"
              size={isCompact ? 'sm' : 'md'}
              onClick={onDismiss}
            >
              Закрыть
            </Button>
          )}
        </div>
      )}
    </div>
  );
};
