import type { FC } from 'react';
import { NavLink } from 'react-router-dom';
import { useBasketProgress } from '@/features/basket/useBasketProgress';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import { cn } from '@/lib/utils';
import { NAV_ITEMS } from '@/constants/navigation';
import { ROUTES } from '@/constants/routes';

function formatBadgeCount(count: number): string {
  return count > 99 ? '99+' : String(count);
}

export const BottomNavigation: FC = () => {
  const { menuPlan } = useMenuPlan();
  const { remainingCount } = useBasketProgress();

  const showBasketBadge = menuPlan !== null && remainingCount > 0;
  const badgeLabel = showBasketBadge
    ? `${remainingCount} ${remainingCount === 1 ? 'товар' : remainingCount < 5 ? 'товара' : 'товаров'} ещё не куплено`
    : undefined;

  return (
    <nav
      className="fixed bottom-0 left-1/2 z-30 w-full max-w-lg -translate-x-1/2 border-t border-app-secondary bg-app-bottom-bar pb-[env(safe-area-inset-bottom)]"
      aria-label="Основная навигация"
    >
      <ul className="flex h-16 items-stretch">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const isBasketTab = path === ROUTES.BASKET;

          return (
            <li key={path} className="flex-1">
              <NavLink
                to={path}
                end={path === ROUTES.HOME}
                className={({ isActive }) =>
                  cn(
                    'relative flex h-full flex-col items-center justify-center gap-0.5 px-1 text-xs transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-app-link',
                    isActive
                      ? 'text-app-link font-semibold'
                      : 'text-app-hint hover:text-app-text',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span className="relative inline-flex">
                      <Icon
                        className={cn('h-5 w-5', isActive && 'stroke-[2.5]')}
                        aria-hidden="true"
                      />
                      {isBasketTab && showBasketBadge && (
                        <span
                          className="absolute -right-2 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-app-button px-1 text-[10px] font-semibold leading-none text-app-button-text"
                          aria-label={badgeLabel}
                        >
                          {formatBadgeCount(remainingCount)}
                        </span>
                      )}
                    </span>
                    <span>{label}</span>
                  </>
                )}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
};
