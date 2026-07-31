import { useMemo, useState, type FC } from 'react';

import { replaceMeal } from '@/api/replaceMeal';
import { Button, Modal, Spinner, Typography } from '@/components/ui';
import { coordinateReplacementSuccess } from '@/features/menu-plan/coordinateReplacementSuccess';
import { matchRecipeForMeal } from '@/features/menu-plan/matchRecipe';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import {
  REASON_PRESETS,
  buildIngredientOptions,
  findReasonPreset,
  shouldShowIngredientSelector,
} from '@/features/menu-plan/replacementReason';
import { useReplaceMealSheet } from '@/features/menu-plan/ReplaceMealSheetContext';
import {
  classifyStrategyWorkflowError,
  StrategyWorkflowErrorPanel,
} from '@/features/strategy-workflow';
import type { StrategyWorkflowError, WorkflowRetryAction } from '@/features/strategy-workflow/types';
import { MEAL_TYPE_LABELS } from '@/types/meal';
import { createRequestId } from '@/lib/requestId';

const OTHER_INGREDIENT = '__other__';

export const ReplaceMealSheet: FC = () => {
  const { isOpen, target, closeSheet } = useReplaceMealSheet();
  const { menuPlan, setMenuPlan } = useMenuPlan();
  const [selectedPreset, setSelectedPreset] = useState<string>('simple');
  const [customReason, setCustomReason] = useState('');
  const [selectedIngredient, setSelectedIngredient] = useState<string | null>(null);
  const [isReplacing, setIsReplacing] = useState(false);
  const [error, setError] = useState<StrategyWorkflowError | null>(null);

  const ingredientOptions = useMemo(() => {
    if (!target || !menuPlan) {
      return [];
    }
    const match = matchRecipeForMeal(target.meal, menuPlan.recipes);
    return buildIngredientOptions(match.recipe);
  }, [target, menuPlan]);

  if (!target || !menuPlan?.strategy_id) {
    return null;
  }

  const mealId = target.meal.meal_id?.trim();
  if (!mealId) {
    return null;
  }

  const activePreset = findReasonPreset(selectedPreset);
  const showIngredientSelector =
    shouldShowIngredientSelector(activePreset?.reasonCode) && ingredientOptions.length > 0;

  const handleClose = () => {
    if (isReplacing) return;
    setError(null);
    setSelectedPreset('simple');
    setCustomReason('');
    setSelectedIngredient(null);
    closeSheet();
  };

  const resolveReason = (): string | undefined => {
    if (!activePreset) return undefined;
    if (activePreset.id === 'other') {
      const trimmed = customReason.trim();
      return trimmed || undefined;
    }
    return activePreset.reason || undefined;
  };

  const resolveTargetIngredient = (): string | undefined => {
    if (!showIngredientSelector) return undefined;
    if (!selectedIngredient || selectedIngredient === OTHER_INGREDIENT) return undefined;
    return selectedIngredient;
  };

  const handleReplace = async () => {
    if (isReplacing || !menuPlan.strategy_id || !mealId) return;

    setIsReplacing(true);
    setError(null);

    try {
      const response = await replaceMeal({
        strategy_id: menuPlan.strategy_id,
        menu_plan: menuPlan,
        meal_id: mealId,
        reason: resolveReason(),
        reason_code: activePreset?.reasonCode,
        target_ingredient: resolveTargetIngredient(),
        replacement_request_id: createRequestId(),
        // Durable plans replace with optimistic concurrency; legacy plans
        // (no menu_plan_id) keep the pre-7.2 contract.
        menu_plan_id: menuPlan.menu_plan_id ?? undefined,
        expected_revision: menuPlan.menu_plan_revision ?? undefined,
      });

      coordinateReplacementSuccess(response.menu_plan, { setMenuPlan });
      handleClose();
    } catch (err: unknown) {
      setError(classifyStrategyWorkflowError(err));
    } finally {
      setIsReplacing(false);
    }
  };

  const handleErrorAction = (action: WorkflowRetryAction) => {
    if (action === 'retry_same_request') {
      void handleReplace();
    }
  };

  const mealLabel = MEAL_TYPE_LABELS[target.meal.type];

  return (
    <Modal open={isOpen} onClose={handleClose} title="Заменить блюдо">
      <div className="flex flex-col gap-4">
        <Typography variant="body" className="text-app-hint">
          {mealLabel}: {target.meal.recipe_name}
        </Typography>

        <div className="flex flex-col gap-2" role="radiogroup" aria-label="Причина замены">
          {REASON_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              role="radio"
              aria-checked={selectedPreset === preset.id}
              disabled={isReplacing}
              onClick={() => {
                setSelectedPreset(preset.id);
                setSelectedIngredient(null);
              }}
              className={`rounded-app border px-3 py-2 text-left transition-colors ${
                selectedPreset === preset.id
                  ? 'border-app-link bg-app-secondary'
                  : 'border-app-secondary bg-app-bg'
              }`}
            >
              <Typography variant="body">{preset.label}</Typography>
            </button>
          ))}
        </div>

        {showIngredientSelector && (
          <fieldset className="flex flex-col gap-2 border-0 p-0">
            <legend className="mb-1">
              <Typography variant="label">Что именно не подходит?</Typography>
            </legend>
            {[...ingredientOptions, OTHER_INGREDIENT].map((option) => {
              const isOther = option === OTHER_INGREDIENT;
              const label = isOther ? 'Другое' : option;
              return (
                <label
                  key={option}
                  className="flex items-center gap-2 rounded-app border border-app-secondary bg-app-bg px-3 py-2"
                >
                  <input
                    type="radio"
                    name="target-ingredient"
                    value={option}
                    disabled={isReplacing}
                    checked={selectedIngredient === option}
                    onChange={() => setSelectedIngredient(option)}
                  />
                  <Typography variant="body">{label}</Typography>
                </label>
              );
            })}
          </fieldset>
        )}

        {selectedPreset === 'other' && (
          <textarea
            value={customReason}
            onChange={(event) => setCustomReason(event.target.value)}
            maxLength={400}
            disabled={isReplacing}
            placeholder="Коротко опишите причину (необязательно)"
            className="min-h-20 w-full rounded-app border border-app-secondary bg-app-bg p-3 text-app-text"
          />
        )}

        {isReplacing && (
          <div className="flex items-center gap-2 py-2">
            <Spinner size="sm" />
            <Typography variant="body">Подбираем замену…</Typography>
          </div>
        )}

        {error && (
          <StrategyWorkflowErrorPanel
            error={error}
            compact
            showRequestId
            onAction={handleErrorAction}
            onDismiss={() => setError(null)}
          />
        )}

        <div className="flex flex-col gap-2">
          <Button type="button" size="full" onClick={() => void handleReplace()} disabled={isReplacing}>
            Заменить блюдо
          </Button>
          <Button type="button" size="full" variant="ghost" onClick={handleClose} disabled={isReplacing}>
            Отмена
          </Button>
        </div>
      </div>
    </Modal>
  );
};
