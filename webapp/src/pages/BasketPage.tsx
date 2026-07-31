import type { FC } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  BasketLoadingSkeleton,
  EmptyState,
  MenuPlanLoadingSkeleton,
  Typography,
} from '@/components/ui';
import { Basket, countBasketItems } from '@/features/basket';
import { useBasketState } from '@/features/basket/useBasketState';
import { useGenerateMenuSheet } from '@/features/menu-generator/GenerateMenuSheetContext';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import { PositiveEventCard } from '@/features/positive-events/PositiveEventCard';
import { usePositiveEvents } from '@/features/positive-events/usePositiveEvents';
import { ROUTES } from '@/constants/routes';

export const BasketPage: FC = () => {
  const navigate = useNavigate();
  const { menuPlan, isMenuPlanHydrated } = useMenuPlan();
  const { isBasketHydrated } = useBasketState();
  const { openSheet } = useGenerateMenuSheet();
  const positiveEvents = usePositiveEvents(menuPlan?.strategy_id);

  if (!isMenuPlanHydrated) {
    return (
      <div className="p-4 pb-8" role="status" aria-live="polite">
        <Typography variant="body" className="mb-4 text-app-hint">
          Собираем список покупок…
        </Typography>
        <MenuPlanLoadingSkeleton />
      </div>
    );
  }

  if (!menuPlan) {
    return (
      <div className="p-4 pb-8">
        <EmptyState
          title="В корзине пока нет продуктов"
          description="Создайте меню, чтобы получить список продуктов для покупок."
          actionLabel="На главную"
          onAction={() => navigate(ROUTES.HOME)}
        />
      </div>
    );
  }

  const itemCount = countBasketItems(menuPlan.basket);
  const categoryCount = menuPlan.basket.length;

  if (categoryCount === 0 || itemCount === 0) {
    return (
      <div className="p-4 pb-8">
        <EmptyState
          title="В корзине пока нет продуктов"
          description="Сервер не вернул продукты для корзины. Попробуйте создать меню заново."
          actionLabel="На главную"
          onAction={() => navigate(ROUTES.HOME)}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4 pb-8">
      <Typography variant="h2">Корзина</Typography>

      {!isBasketHydrated ? (
        <div role="status" aria-live="polite">
          <Typography variant="body" className="mb-3 text-app-hint">
            Собираем список покупок…
          </Typography>
          <BasketLoadingSkeleton />
        </div>
      ) : (
        <Basket
          categories={menuPlan.basket}
          totalCost={menuPlan.total_cost}
          recipeCost={menuPlan.recipe_cost}
          shoppingCost={menuPlan.shopping_cost ?? menuPlan.total_cost}
        />
      )}

      {menuPlan.strategy_id && (
        <PositiveEventCard
          eventType="shopping_completed"
          title="Закупка"
          description="Отметьте, когда купите продукты по списку — это подтвердит, что план закупок сработал."
          actionLabel="Закупка выполнена"
          markedLabel="Закупка отмечена выполненной"
          events={positiveEvents}
        />
      )}

      <div className="flex flex-col gap-2">
        <Button type="button" size="full" variant="secondary" onClick={() => navigate(ROUTES.RECIPES)}>
          Перейти к рецептам
        </Button>
        <Button type="button" size="full" variant="ghost" onClick={openSheet}>
          Создать новое меню
        </Button>
      </div>
    </div>
  );
};
