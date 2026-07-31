import { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { ROUTE_META, ROUTES, type AppRoute } from '@/constants/routes';

export function usePageTitle(): string {
  const { pathname } = useLocation();

  return useMemo(() => {
    const matchedRoute = (Object.values(ROUTES) as AppRoute[]).find(
      (route) => route === pathname,
    );

    if (matchedRoute) {
      return ROUTE_META[matchedRoute].title;
    }

    return ROUTE_META[ROUTES.HOME].title;
  }, [pathname]);
}
