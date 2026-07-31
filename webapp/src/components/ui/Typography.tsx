import type { ElementType, FC, HTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const typographyVariants = cva('text-app-text', {
  variants: {
    variant: {
      h1: 'text-2xl font-bold tracking-tight',
      h2: 'text-xl font-semibold tracking-tight',
      h3: 'text-lg font-semibold',
      body: 'text-base font-normal',
      caption: 'text-sm font-normal',
      label: 'text-sm font-medium',
    },
  },
  defaultVariants: {
    variant: 'body',
  },
});

const defaultElements = {
  h1: 'h1',
  h2: 'h2',
  h3: 'h3',
  body: 'p',
  caption: 'p',
  label: 'span',
} as const satisfies Record<string, ElementType>;

type TypographyVariant = NonNullable<VariantProps<typeof typographyVariants>['variant']>;

export interface TypographyProps
  extends HTMLAttributes<HTMLElement>,
    VariantProps<typeof typographyVariants> {
  as?: ElementType;
}

export const Typography: FC<TypographyProps> = ({
  className,
  variant = 'body',
  as,
  children,
  ...props
}) => {
  const resolvedVariant: TypographyVariant = variant ?? 'body';
  const Component = as ?? defaultElements[resolvedVariant];

  return (
    <Component
      className={cn(typographyVariants({ variant: resolvedVariant }), className)}
      {...props}
    >
      {children}
    </Component>
  );
};

export { typographyVariants };
