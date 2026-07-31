import type { FC } from 'react';
import { cn } from '@/lib/utils';

export interface SegmentedControlOption<T extends string | number> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string | number> {
  options: readonly SegmentedControlOption<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
  className?: string;
  'aria-label'?: string;
}

export function SegmentedControl<T extends string | number>({
  options,
  value,
  onChange,
  disabled = false,
  className,
  'aria-label': ariaLabel,
}: SegmentedControlProps<T>): ReturnType<FC> {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        'inline-flex w-full rounded-app bg-app-secondary p-1',
        disabled && 'pointer-events-none opacity-50',
        className,
      )}
    >
      {options.map((option) => {
        const isSelected = option.value === value;

        return (
          <button
            key={String(option.value)}
            type="button"
            disabled={disabled}
            aria-pressed={isSelected}
            onClick={() => onChange(option.value)}
            className={cn(
              'flex-1 rounded-[calc(var(--app-radius)-2px)] px-2 py-2 text-sm font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link',
              isSelected
                ? 'bg-app-bg text-app-text shadow-sm'
                : 'text-app-hint hover:text-app-text',
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
