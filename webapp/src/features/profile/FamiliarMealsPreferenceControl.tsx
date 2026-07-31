import type { FC } from 'react';

import { Typography } from '@/components/ui';
import {
  FAMILIAR_MEALS_OPTIONS,
  familiarMealsPreferenceDescription,
  familiarMealsPreferenceFromProfile,
  planningPreferencesFromFamiliarMealsValue,
  type FamiliarMealsPreferenceValue,
} from '@/features/profile/familiarMealsPreference';
import { cn } from '@/lib/utils';
import type { PlanningPreferences } from '@/types/profile';

export interface FamiliarMealsPreferenceControlProps {
  value: PlanningPreferences;
  onChange: (preferences: PlanningPreferences) => void;
  disabled?: boolean;
}

export const FamiliarMealsPreferenceControl: FC<FamiliarMealsPreferenceControlProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  const selected = familiarMealsPreferenceFromProfile(value);
  const description = familiarMealsPreferenceDescription(selected);

  const handleSelect = (next: FamiliarMealsPreferenceValue) => {
    if (disabled) return;
    onChange(planningPreferencesFromFamiliarMealsValue(next));
  };

  return (
    <div className="flex flex-col gap-3">
      <div
        role="radiogroup"
        aria-label="Предпочтение знакомых блюд"
        className={cn('flex flex-col gap-2', disabled && 'opacity-50')}
      >
        {FAMILIAR_MEALS_OPTIONS.map((option) => {
          const isChecked = selected === option.value;
          const inputId = `familiar-meals-${option.value}`;

          return (
            <label
              key={option.value}
              htmlFor={inputId}
              className={cn(
                'flex cursor-pointer items-start gap-3 rounded-app-lg border border-app-border p-3 transition-colors',
                isChecked && 'border-app-link bg-app-secondary/60',
                disabled && 'pointer-events-none',
              )}
            >
              <input
                id={inputId}
                type="radio"
                name="familiar-meals-preference"
                className="mt-1 h-4 w-4 accent-app-button"
                checked={isChecked}
                disabled={disabled}
                onChange={() => handleSelect(option.value)}
              />
              <span className="min-w-0">
                <Typography variant="label">{option.label}</Typography>
              </span>
            </label>
          );
        })}
      </div>
      <Typography variant="caption" className="text-app-hint" id="familiar-meals-description">
        {description}
      </Typography>
    </div>
  );
};
