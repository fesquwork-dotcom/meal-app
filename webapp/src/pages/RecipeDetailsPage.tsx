import type { FC } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, EmptyState, MenuPlanLoadingSkeleton, Typography } from '@/components/ui';
import { RecipeCard } from '@/features/recipes';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import { parseRecipeIndexParam, ROUTES } from '@/constants/routes';

export const RecipeDetailsPage: FC = () => {
  const navigate = useNavigate();
  const { recipeIndex: recipeIndexParam } = useParams<{ recipeIndex: string }>();
  const { menuPlan, isMenuPlanHydrated } = useMenuPlan();

  const recipeIndex = parseRecipeIndexParam(recipeIndexParam);

  if (!isMenuPlanHydrated) {
    return <MenuPlanLoadingSkeleton />;
  }

  if (!menuPlan) {
    return (
      <div className="p-4">
        <EmptyState
          title="Меню не найдено"
          description="Сначала создайте меню на главной странице."
          actionLabel="На главную"
          onAction={() => navigate(ROUTES.HOME)}
        />
      </div>
    );
  }

  if (recipeIndex === null) {
    return (
      <div className="p-4">
        <EmptyState
          title="Рецепт не найден"
          description="Некорректная ссылка на рецепт."
          actionLabel="К списку рецептов"
          onAction={() => navigate(ROUTES.RECIPES)}
        />
      </div>
    );
  }

  const recipe = menuPlan.recipes[recipeIndex];

  if (!recipe) {
    return (
      <div className="p-4">
        <EmptyState
          title="Рецепт не найден"
          description="Такого рецепта нет в текущем меню."
          actionLabel="К списку рецептов"
          onAction={() => navigate(ROUTES.RECIPES)}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4 pb-8">
      <div className="min-w-0">
        <Typography variant="h1" className="break-words">
          {recipe.emoji ? `${recipe.emoji} ` : ''}
          {recipe.name}
        </Typography>
      </div>

      <RecipeCard recipe={recipe} fullyExpanded hideTitle />

      <div className="flex flex-col gap-2">
        <Button type="button" size="full" variant="secondary" onClick={() => navigate(ROUTES.RECIPES)}>
          Назад к рецептам
        </Button>
        <Button type="button" size="full" variant="ghost" onClick={() => navigate(ROUTES.BASKET)}>
          Перейти в корзину
        </Button>
      </div>
    </div>
  );
};
