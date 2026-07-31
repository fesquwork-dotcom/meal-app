import type { FC } from 'react';
import { Minus, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface StepperProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  disabled?: boolean;
  className?: string;
  'aria-label'?: string;
}

export const Stepper: FC<StepperProps> = ({
  value,
  onChange,
  min = 1,
  max = 99,
  disabled = false,
  className,
  'aria-label': ariaLabel,
}) => {
  const decrement = () => onChange(Math.max(min, value - 1));
  const increment = () => onChange(Math.min(max, value + 1));

  return (
    <div
      className={cn(
        'inline-flex items-center gap-3 rounded-app bg-app-secondary px-2 py-1',
        disabled && 'pointer-events-none opacity-50',
        className,
      )}
      aria-label={ariaLabel}
    >
      <button
        type="button"
        disabled={disabled || value <= min}
        onClick={decrement}
        aria-label="Уменьшить"
        className={cn(
          'flex h-9 w-9 items-center justify-center rounded-app text-app-text transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link',
          'disabled:opacity-40',
          'hover:bg-app-bg',
        )}
      >
        <Minus className="h-4 w-4" aria-hidden="true" />
      </button>

      <span
        className="min-w-[2rem] text-center text-base font-semibold tabular-nums"
        aria-live="polite"
      >
        {value}
      </span>

      <button
        type="button"
        disabled={disabled || value >= max}
        onClick={increment}
        aria-label="Увеличить"
        className={cn(
          'flex h-9 w-9 items-center justify-center rounded-app text-app-text transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link',
          'disabled:opacity-40',
          'hover:bg-app-bg',
        )}
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
};
