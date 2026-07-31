import { useEffect, type FC, type MouseEvent, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { Typography } from '@/components/ui/Typography';
import { cn } from '@/lib/utils';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  titleId?: string;
  children: ReactNode;
  className?: string;
  overlayClassName?: string;
}

export const Modal: FC<ModalProps> = ({
  open,
  onClose,
  title,
  titleId = 'modal-title',
  children,
  className,
  overlayClassName,
}) => {
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const handleOverlayClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4',
        overlayClassName,
      )}
      onClick={handleOverlayClick}
      aria-hidden={false}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn(
          'flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-app-lg bg-app-bg shadow-lg sm:rounded-app-lg',
          className,
        )}
      >
        <div className="flex items-center justify-between border-b border-app-secondary px-4 py-3">
          <Typography variant="h3" id={titleId}>
            {title}
          </Typography>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className={cn(
              'flex h-9 w-9 items-center justify-center rounded-app text-app-hint transition-colors',
              'hover:bg-app-secondary hover:text-app-text',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link',
            )}
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="overflow-y-auto px-4 py-4">{children}</div>
      </div>
    </div>
  );
};
