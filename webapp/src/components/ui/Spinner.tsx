import type { FC, HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface SpinnerProps extends HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg';
}

const sizeClasses = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-8 w-8 border-[3px]',
};

export const Spinner: FC<SpinnerProps> = ({ className, size = 'md', ...props }) => (
  <div
    role="status"
    aria-label="Загрузка"
    className={cn('inline-block animate-spin rounded-full border-app-button border-t-transparent', sizeClasses[size], className)}
    {...props}
  />
);
