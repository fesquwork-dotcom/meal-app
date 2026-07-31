import type { FC } from 'react';
import { cn } from '@/lib/utils';

export interface MainButtonSlotProps {
  className?: string;
}

/**
 * Reserved area for the future Telegram WebApp MainButton.
 * SDK integration will mount the native button into this slot.
 */
export const MainButtonSlot: FC<MainButtonSlotProps> = ({ className }) => (
  <div
    id="telegram-main-button-slot"
    className={cn(
      'pointer-events-none fixed bottom-16 left-1/2 z-20 h-14 w-full max-w-lg -translate-x-1/2',
      className,
    )}
    aria-hidden="true"
  />
);
