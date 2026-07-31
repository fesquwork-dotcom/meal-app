import { useMemo, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, EmptyState, Input, MenuPlanLoadingSkeleton, Section } from '@/components/ui';
import { RecipeCard } from '@/features/recipes';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import { recipeDetailPath, ROUTES } from '@/constants/routes';
import { pluralize } from '@/utils/pluralize';
import type { Recipe } from '@/types/recipe';

interface FilteredRecipe {
  recipe: Recipe;
  originalIndex: number;
}

export const RecipesPage: FC = () => {
  const navigate = useNavigate();
  const { menuPlan, isMenuPlanHydrated } = useMenuPlan();
  const [search, setSearch] = useState('');

  const filteredRecipes = useMemo((): FilteredRecipe[] => {
    if (!menuPlan) return [];

    const query = search.trim().toLowerCase();
    return menuPlan.recipes
      .map((recipe, originalIndex) => ({ recipe, originalIndex }))
      .filter(({ recipe }) =>
        query ? recipe.name.toLowerCase().includes(query) : true,
      );
  }, [menuPlan, search]);

  if (!isMenuPlanHydrated) {
    return <MenuPlanLoadingSkeleton />;
  }

  if (!menuPlan) {
    return (
      <div className="p-4">
        <EmptyState
          title="Рецептов пока нет"
          description="Сначала создайте меню — рецепты появятся здесь автоматически."
          actionLabel="На главную"
          onAction={() => navigate(ROUTES.HOME)}
        />
      </div>
    );
  }

  if (menuPlan.recipes.length === 0) {
    return (
      <div className="p-4">
        <EmptyState
          title="Рецепты не получены"
          description="Сервер вернул меню без рецептов. Попробуйте создать меню заново."
          actionLabel="На главную"
          onAction={() => navigate(ROUTES.HOME)}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4 pb-8">
      <Section
        title="Рецепты"
        description={pluralize(menuPlan.recipes.length, ['рецепт', 'рецепта', 'рецептов'])}
      />

      <div className="flex gap-2">
        <Input
          type="search"
          placeholder="Поиск по названию…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Поиск рецептов"
          className="flex-1"
        />
        {search && (
          <Button type="button" variant="ghost" onClick={() => setSearch('')}>
            Очистить
          </Button>
        )}
      </div>

      {filteredRecipes.length === 0 ? (
        <EmptyState
          title="Ничего не найдено"
          description={`Нет рецептов по запросу «${search}».`}
          actionLabel="Очистить поиск"
          onAction={() => setSearch('')}
        />
      ) : (
        <div className="flex flex-col gap-3">
          {filteredRecipes.map(({ recipe, originalIndex }, listIndex) => (
            <RecipeCard
              key={`${recipe.name}-${originalIndex}`}
              recipe={recipe}
              index={listIndex}
              compact
              showDetailsAction
              onOpenDetails={() => navigate(recipeDetailPath(originalIndex))}
            />
          ))}
        </div>
      )}
    </div>
  );
};
