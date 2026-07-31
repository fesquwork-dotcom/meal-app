import { Button, Typography } from '@/components/ui';
import { StrategyWorkflowErrorPanel } from '@/features/strategy-workflow/StrategyWorkflowErrorPanel';
import type { ProfileConflictState } from '@/features/strategy-workflow/workflowSuccessTypes';
import type { FC } from 'react';

export interface ProfileConflictDialogProps {
  open: boolean;
  conflict: ProfileConflictState | null;
  rebasePending: boolean;
  onReloadServer: () => void;
  onKeepLocal: () => void;
  onConfirmRebase: () => void;
  onCancelRebase: () => void;
}

export const ProfileConflictDialog: FC<ProfileConflictDialogProps> = ({
  open,
  conflict,
  rebasePending,
  onReloadServer,
  onKeepLocal,
  onConfirmRebase,
  onCancelRebase,
}) => {
  if (!open || !conflict) {
    return null;
  }

  return (
    <section
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="profile-conflict-heading"
      aria-describedby="profile-conflict-description"
      className="rounded-app-lg border border-app-warning/40 bg-app-secondary p-4"
    >
      <Typography id="profile-conflict-heading" variant="h3" className="mb-2">
        Настройки изменились в другой сессии
      </Typography>
      <div id="profile-conflict-description" className="mb-4">
        <StrategyWorkflowErrorPanel
          error={conflict.error}
          variant="inline"
          showRequestId={false}
        />
        <Typography variant="caption" className="mt-2 text-app-hint">
          Сохранённая ревизия: {conflict.details.currentRevision}
        </Typography>
      </div>

      {rebasePending ? (
        <div className="flex flex-col gap-2">
          <Typography variant="body" className="text-app-warning" role="status">
            Повторное сохранение заменит настройки из другой сессии.
          </Typography>
          <Button type="button" size="full" onClick={onConfirmRebase}>
            Сохранить мои изменения
          </Button>
          <Button type="button" variant="secondary" size="full" onClick={onCancelRebase}>
            Отмена
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Button type="button" size="full" onClick={onReloadServer}>
            Загрузить сохранённые настройки
          </Button>
          <Button type="button" variant="secondary" size="full" onClick={onKeepLocal}>
            Оставить мои изменения
          </Button>
        </div>
      )}
    </section>
  );
};
