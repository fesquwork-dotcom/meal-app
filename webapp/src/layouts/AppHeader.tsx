import type { FC } from 'react';
import { useRouteMeta } from '@/hooks/useRouteMeta';
import { Typography } from '@/components/ui';

export const AppHeader: FC = () => {
  const { showHeader, title } = useRouteMeta();

  if (!showHeader) {
    return null;
  }

  return (
    <header className="sticky top-0 z-20 border-b border-app-secondary bg-app-header-bg/95 px-4 py-3 backdrop-blur-sm pt-[max(0.75rem,env(safe-area-inset-top))]">
      <Typography variant="h2" className="text-center">
        {title}
      </Typography>
    </header>
  );
};
