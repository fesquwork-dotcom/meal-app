import type { FC } from 'react';

import { Typography } from '@/components/ui';
import {
  COOKING_SPEED_OPTIONS,
  cookingSpeedPreferenceDescription,
  cookingSpeedPreferenceFromProfile,
  cookingPreferencesFromSpeedPreference,
  type CookingSpeedPreferenceValue,
} from '@/features/profile/cookingSpeedPreference';
import { cn } from '@/lib/utils';
import type { CookingPreferences } from '@/types/profile';

export interface CookingSpeedPreferenceControlProps {
  value: CookingPreferences;
  onChange: (preferences: CookingPreferences) => void;
  disabled?: boolean;
}

export const CookingSpeedPreferenceControl: FC<CookingSpeedPreferenceControlProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  const selected = cookingSpeedPreferenceFromProfile(value);
  const description = cookingSpeedPreferenceDescription(selected);

  const handleSelect = (next: CookingSpeedPreferenceValue) => {
    if (disabled) return;
    onChange(cookingPreferencesFromSpeedPreference(next));
  };

  return (
    <div className="flex flex-col gap-3">
      <div
        role="radiogroup"
        aria-label="Выбирать более быстрые блюда"
        className={cn('flex flex-col gap-2', disabled && 'opacity-50')}
      >
        {COOKING_SPEED_OPTIONS.map((option) => {
          const isChecked = selected === option.value;
          const inputId = `cooking-speed-${option.value}`;

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
                name="cooking-speed-preference"
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
      <Typography variant="caption" className="text-app-hint" id="cooking-speed-description">
        {description}
      </Typography>
    </div>
  );
};
