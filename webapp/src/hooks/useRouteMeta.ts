import { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import {
  isMenuHistoryDetailPath,
  isRecipeDetailPath,
  MENU_HISTORY_DETAIL_TITLE,
  RECIPE_DETAIL_TITLE,
  ROUTE_META,
  ROUTES,
  type AppRoute,
  type RouteMeta,
} from '@/constants/routes';

function resolveRouteMeta(pathname: string): RouteMeta {
  if (isRecipeDetailPath(pathname)) {
    return { showHeader: true, title: RECIPE_DETAIL_TITLE };
  }

  if (isMenuHistoryDetailPath(pathname)) {
    return { showHeader: true, title: MENU_HISTORY_DETAIL_TITLE };
  }

  const matchedRoute = (Object.values(ROUTES) as AppRoute[]).find(
    (route) => route === pathname,
  );

  if (matchedRoute) {
    return ROUTE_META[matchedRoute];
  }

  return ROUTE_META[ROUTES.HOME];
}

export function useRouteMeta(): RouteMeta {
  const { pathname } = useLocation();
  return useMemo(() => resolveRouteMeta(pathname), [pathname]);
}
