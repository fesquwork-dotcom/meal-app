import type { FC, HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {}

export const Card: FC<CardProps> = ({ className, ...props }) => (
  <div
    className={cn('rounded-app-lg bg-app-secondary text-app-text', className)}
    {...props}
  />
);

export interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {}

export const CardHeader: FC<CardHeaderProps> = ({ className, ...props }) => (
  <div className={cn('flex flex-col gap-1 p-4 pb-0', className)} {...props} />
);

export interface CardTitleProps extends HTMLAttributes<HTMLHeadingElement> {}

export const CardTitle: FC<CardTitleProps> = ({ className, ...props }) => (
  <h3
    className={cn('text-lg font-semibold leading-none tracking-tight', className)}
    {...props}
  />
);

export interface CardDescriptionProps extends HTMLAttributes<HTMLParagraphElement> {}

export const CardDescription: FC<CardDescriptionProps> = ({ className, ...props }) => (
  <p className={cn('text-sm text-app-hint', className)} {...props} />
);

export interface CardContentProps extends HTMLAttributes<HTMLDivElement> {}

export const CardContent: FC<CardContentProps> = ({ className, ...props }) => (
  <div className={cn('p-4', className)} {...props} />
);

export interface CardFooterProps extends HTMLAttributes<HTMLDivElement> {}

export const CardFooter: FC<CardFooterProps> = ({ className, ...props }) => (
  <div className={cn('flex items-center p-4 pt-0', className)} {...props} />
);
