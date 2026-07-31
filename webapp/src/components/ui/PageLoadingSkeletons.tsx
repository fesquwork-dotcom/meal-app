import type { FC, ReactNode } from 'react';
import { Skeleton } from '@/components/ui/Skeleton';

export interface MenuPlanLoadingSkeletonProps {
  label?: string;
  children?: ReactNode;
}

export const MenuPlanLoadingSkeleton: FC<MenuPlanLoadingSkeletonProps> = ({
  label = 'Загружаем сохранённое меню…',
  children,
}) => (
  <div className="flex flex-col gap-4 p-4" aria-busy="true">
    <span className="sr-only">{label}</span>
    {children ?? (
      <>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </>
    )}
  </div>
);

export const BasketLoadingSkeleton: FC = () => (
  <div className="flex flex-col gap-4" aria-busy="true">
    <span className="sr-only">Загружаем состояние корзины…</span>
    <Skeleton className="h-20 w-full" />
    <Skeleton className="h-32 w-full" />
    <Skeleton className="h-32 w-full" />
  </div>
);
