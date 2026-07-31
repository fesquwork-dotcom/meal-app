import { useEffect, type FC } from 'react';
import { Button, Typography } from '@/components/ui';
import { cn } from '@/lib/utils';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: FC<ConfirmDialogProps> = ({
  open,
  title,
  description,
  confirmLabel = 'Удалить',
  cancelLabel = 'Отмена',
  onConfirm,
  onCancel,
}) => {
  const titleId = 'confirm-dialog-title';
  const descriptionId = 'confirm-dialog-description';

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onCancel();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onCancel]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4"
      onClick={onCancel}
      aria-hidden={false}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className={cn(
          'w-full max-w-lg rounded-t-app-lg bg-app-bg p-4 shadow-lg sm:rounded-app-lg',
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <Typography variant="h3" id={titleId}>
          {title}
        </Typography>
        <Typography variant="body" id={descriptionId} className="mt-2 text-app-hint">
          {description}
        </Typography>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row-reverse">
          <Button
            type="button"
            variant="destructive"
            size="full"
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
          <Button type="button" variant="secondary" size="full" onClick={onCancel}>
            {cancelLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};
