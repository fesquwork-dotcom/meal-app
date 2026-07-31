/** Application route paths. */
export const ROUTES = {
  HOME: '/',
  WEEK: '/week',
  BASKET: '/basket',
  RECIPES: '/recipes',
  PROFILE: '/profile',
  PROGRESS: '/progress',
  HISTORY: '/history',
} as const;

export type AppRoute = (typeof ROUTES)[keyof typeof ROUTES];

export const PAGE_TITLES: Record<AppRoute, string> = {
  [ROUTES.HOME]: 'Сегодня',
  [ROUTES.WEEK]: 'Неделя',
  [ROUTES.BASKET]: 'Корзина',
  [ROUTES.RECIPES]: 'Рецепты',
  [ROUTES.PROFILE]: 'Профиль',
  [ROUTES.PROGRESS]: 'Мой прогресс',
  [ROUTES.HISTORY]: 'История планов',
};

export const RECIPE_DETAIL_TITLE = 'Рецепт';
export const MENU_HISTORY_DETAIL_TITLE = 'План недели';

export interface RouteMeta {
  showHeader: boolean;
  title: string;
}

export const ROUTE_META: Record<AppRoute, RouteMeta> = {
  [ROUTES.HOME]: { showHeader: false, title: PAGE_TITLES[ROUTES.HOME] },
  [ROUTES.WEEK]: { showHeader: true, title: PAGE_TITLES[ROUTES.WEEK] },
  [ROUTES.BASKET]: { showHeader: true, title: PAGE_TITLES[ROUTES.BASKET] },
  [ROUTES.RECIPES]: { showHeader: true, title: PAGE_TITLES[ROUTES.RECIPES] },
  [ROUTES.PROFILE]: { showHeader: true, title: PAGE_TITLES[ROUTES.PROFILE] },
  [ROUTES.PROGRESS]: { showHeader: true, title: PAGE_TITLES[ROUTES.PROGRESS] },
  [ROUTES.HISTORY]: { showHeader: true, title: PAGE_TITLES[ROUTES.HISTORY] },
};

export function recipeDetailPath(recipeIndex: number): string {
  return `${ROUTES.RECIPES}/${recipeIndex}`;
}

export function isRecipeDetailPath(pathname: string): boolean {
  return pathname.startsWith(`${ROUTES.RECIPES}/`);
}

export function menuHistoryDetailPath(menuPlanId: string): string {
  return `${ROUTES.HISTORY}/${encodeURIComponent(menuPlanId)}`;
}

export function isMenuHistoryDetailPath(pathname: string): boolean {
  return pathname.startsWith(`${ROUTES.HISTORY}/`);
}

export function parseRecipeIndexParam(value: string | undefined): number | null {
  if (!value) {
    return null;
  }

  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed < 0) {
    return null;
  }

  return parsed;
}
