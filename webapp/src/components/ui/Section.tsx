import type { FC, HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Typography } from '@/components/ui/Typography';

export interface SectionProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: ReactNode;
  description?: ReactNode;
}

export const Section: FC<SectionProps> = ({
  className,
  title,
  description,
  children,
  ...props
}) => (
  <section className={cn('flex flex-col gap-4', className)} {...props}>
    {(title ?? description) && (
      <header className="flex flex-col gap-1">
        {title && (
          <Typography variant="h3" as="h2">
            {title}
          </Typography>
        )}
        {description && (
          <Typography variant="caption" className="text-app-hint">
            {description}
          </Typography>
        )}
      </header>
    )}
    {children}
  </section>
);
