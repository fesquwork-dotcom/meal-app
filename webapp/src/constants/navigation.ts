import {
  CalendarDays,
  CalendarRange,
  ChefHat,
  ShoppingCart,
  User,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { ROUTES, type AppRoute } from '@/constants/routes';

export interface NavItem {
  path: AppRoute;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { path: ROUTES.HOME, label: 'Сегодня', icon: CalendarDays },
  { path: ROUTES.WEEK, label: 'Неделя', icon: CalendarRange },
  { path: ROUTES.BASKET, label: 'Корзина', icon: ShoppingCart },
  { path: ROUTES.RECIPES, label: 'Рецепты', icon: ChefHat },
  { path: ROUTES.PROFILE, label: 'Профиль', icon: User },
];
