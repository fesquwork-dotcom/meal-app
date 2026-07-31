import type { ButtonHTMLAttributes, FC } from 'react';
import { cn } from '@/lib/utils';

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean;
}

export const Chip: FC<ChipProps> = ({
  className,
  selected = false,
  type = 'button',
  disabled,
  ...props
}) => (
  <button
    type={type}
    disabled={disabled}
    aria-pressed={selected}
    className={cn(
      'inline-flex items-center justify-center rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg',
      'disabled:pointer-events-none disabled:opacity-50',
      selected
        ? 'bg-app-button text-app-button-text'
        : 'bg-app-secondary text-app-text hover:opacity-90',
      className,
    )}
    {...props}
  />
);
