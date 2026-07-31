import type { FC } from 'react';
import { Clock, Flame, Lightbulb } from 'lucide-react';
import { motion } from 'framer-motion';
import { Accordion, Button, Card, CardContent, Typography } from '@/components/ui';
import {
  formatCalories,
  formatCookTime,
  groupIngredients,
} from '@/features/recipes/ingredientPresentation';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import { pluralForm } from '@/utils/pluralize';
import type { Recipe } from '@/types/recipe';

export interface RecipeCardProps {
  recipe: Recipe;
  index?: number;
  defaultExpanded?: boolean;
  fullyExpanded?: boolean;
  compact?: boolean;
  showDetailsAction?: boolean;
  onOpenDetails?: () => void;
  hideTitle?: boolean;
}

export const RecipeCard: FC<RecipeCardProps> = ({
  recipe,
  index = 0,
  defaultExpanded = false,
  fullyExpanded = false,
  compact = false,
  showDetailsAction = false,
  onOpenDetails,
  hideTitle = false,
}) => {
  const prefersReducedMotion = usePrefersReducedMotion();
  const ingredientCount = recipe.ingredients.length;
  const stepCount = recipe.steps.length;
  const expandIngredients = fullyExpanded || defaultExpanded;
  const expandSteps = fullyExpanded || (defaultExpanded && stepCount > 0);
  const cookTime = formatCookTime(recipe.cook_time);
  const calories = formatCalories(recipe.calories_per_portion);
  const ingredientGroups = groupIngredients(recipe.ingredients);
  const tips = recipe.tips ?? [];
  const substitutes = recipe.substitutes ?? [];

  const metaRow = (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-app-hint">
      {cookTime && (
        <span className="inline-flex items-center gap-1">
          <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <Typography variant="caption">{cookTime}</Typography>
        </span>
      )}
      {calories && (
        <span className="inline-flex items-center gap-1">
          <Flame className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <Typography variant="caption">{calories}</Typography>
        </span>
      )}
      {recipe.kbju && (
        <Typography variant="caption" className="text-app-hint">
          {recipe.kbju}
        </Typography>
      )}
    </div>
  );

  const content = (
    <Card>
      <CardContent className="pt-4">
        <div className="flex gap-3">
          <span className="text-3xl leading-none" aria-hidden="true">
            {recipe.emoji || '🍽'}
          </span>
          <div className="min-w-0 flex-1">
            {!hideTitle && (
              <Typography variant="h3" className="break-words">
                {recipe.name}
              </Typography>
            )}
            {metaRow}
            {compact && (
              <Typography variant="caption" className="mt-1 text-app-hint">
                {ingredientCount > 0
                  ? `${ingredientCount} ${pluralForm(ingredientCount, ['ингредиент', 'ингредиента', 'ингредиентов'])}`
                  : 'Без ингредиентов'}
                {stepCount > 0
                  ? ` · ${stepCount} ${pluralForm(stepCount, ['шаг', 'шага', 'шагов'])}`
                  : ''}
              </Typography>
            )}
          </div>
        </div>

        {!compact && recipe.description?.trim() && (
          <Typography variant="body" className="mt-3 break-words text-app-subtitle">
            {recipe.description.trim()}
          </Typography>
        )}

        {!compact && (
          <>
            <Accordion
              title="Что понадобится"
              defaultOpen={expandIngredients}
              badge={
                ingredientCount > 0 ? (
                  <span className="rounded-app bg-app-bg px-2 py-0.5 text-xs text-app-hint">
                    {ingredientCount}
                  </span>
                ) : undefined
              }
            >
              {ingredientCount === 0 ? (
                <Typography variant="caption" className="text-app-hint">
                  Ингредиенты не указаны
                </Typography>
              ) : (
                <div className="flex flex-col gap-4">
                  {ingredientGroups.map((group) => (
                    <div key={group.id} className="flex flex-col gap-2">
                      {ingredientGroups.length > 1 && (
                        <Typography variant="caption" className="font-medium text-app-section-header">
                          {group.title}
                        </Typography>
                      )}
                      <ul className="flex flex-col gap-2">
                        {group.items.map((ingredient, i) => (
                          <li
                            key={`${group.id}-${ingredient.name}-${i}`}
                            className="flex items-start justify-between gap-3 border-b border-app-secondary pb-2 last:border-b-0 last:pb-0"
                          >
                            <div className="min-w-0 flex-1">
                              <Typography variant="body" className="break-words">
                                {ingredient.name}
                                {ingredient.amount ? ` — ${ingredient.amount}` : ''}
                              </Typography>
                              {ingredient.note && (
                                <Typography variant="caption" className="text-app-hint">
                                  ({ingredient.note})
                                </Typography>
                              )}
                              {ingredient.pantryLabel && (
                                <Typography variant="caption" className="text-app-accent">
                                  {ingredient.pantryLabel}
                                </Typography>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </Accordion>

            <Accordion
              title="Приготовление"
              defaultOpen={expandSteps}
              badge={
                stepCount > 0 ? (
                  <span className="rounded-app bg-app-bg px-2 py-0.5 text-xs text-app-hint">
                    {stepCount}
                  </span>
                ) : undefined
              }
            >
              {stepCount === 0 ? (
                <Typography variant="caption" className="text-app-hint">
                  Шаги не указаны
                </Typography>
              ) : (
                <ol className="flex flex-col">
                  {recipe.steps.map((step, i) => (
                    <li
                      key={i}
                      className="border-b border-app-secondary py-3 last:border-b-0 last:pb-0 first:pt-0"
                    >
                      <div className="flex gap-3">
                        <span
                          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-app-secondary text-sm font-semibold text-app-accent"
                          aria-hidden="true"
                        >
                          {i + 1}
                        </span>
                        <Typography variant="body" className="min-w-0 break-words pt-0.5">
                          {step}
                        </Typography>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </Accordion>

            {tips.length > 0 && (
              <div className="mt-3 rounded-app bg-app-secondary px-3 py-3">
                <div className="mb-1 flex items-center gap-2 text-app-accent">
                  <Lightbulb className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <Typography variant="caption" className="font-medium">
                    Совет
                  </Typography>
                </div>
                {tips.map((tip, tipIndex) => (
                  <Typography
                    key={tipIndex}
                    variant="body"
                    className="break-words text-app-text"
                  >
                    {tip}
                  </Typography>
                ))}
              </div>
            )}

            {substitutes.length > 0 && (
              <div className="mt-3">
                <Typography variant="caption" className="mb-2 font-medium text-app-section-header">
                  Можно заменить
                </Typography>
                <ul className="flex flex-col gap-3">
                  {substitutes.map((item, i) => (
                    <li key={`${item.original}-${item.replacement}-${i}`} className="text-app-text">
                      <Typography variant="body" className="break-words">
                        {item.original}
                      </Typography>
                      <Typography variant="caption" className="text-app-hint">
                        ↓
                      </Typography>
                      <Typography variant="body" className="break-words">
                        {item.replacement}
                      </Typography>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}

        {showDetailsAction && onOpenDetails && (
          <Button
            type="button"
            variant="secondary"
            size="full"
            className="mt-3"
            onClick={onOpenDetails}
          >
            Открыть полностью
          </Button>
        )}
      </CardContent>
    </Card>
  );

  if (prefersReducedMotion) {
    return content;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05, ease: 'easeOut' }}
    >
      {content}
    </motion.div>
  );
};
