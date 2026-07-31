import { useState, type FC } from 'react';
import {
  Card,
  CardContent,
  Chip,
  Input,
  Section,
  SegmentedControl,
  Stepper,
  Typography,
} from '@/components/ui';
import {
  COOKTIME_OPTIONS,
  GOAL_OPTIONS,
  MEAL_TYPE_OPTIONS,
  PROFILE_BUDGET,
  PROFILE_DAYS,
  PROFILE_PERSONS,
  PROTEIN_OPTIONS,
  STORE_OPTIONS,
} from '@/features/profile/constants';
import { DietaryConstraintsEditor } from '@/features/profile/DietaryConstraintsEditor';
import { CookingSpeedPreferenceControl } from '@/features/profile/CookingSpeedPreferenceControl';
import { FamiliarMealsPreferenceControl } from '@/features/profile/FamiliarMealsPreferenceControl';
import { cn } from '@/lib/utils';
import type { MealType } from '@/types/meal';
import type { Profile, ProfileCooktime, ProfileGoal, ProfileProtein } from '@/types/profile';

export interface ProfileFormProps {
  value: Profile;
  onChange: (profile: Profile) => void;
  disabled?: boolean;
  fieldErrors?: Record<string, string>;
}

function toggleProtein(current: ProfileProtein[], protein: ProfileProtein): ProfileProtein[] {
  if (protein === 'any') {
    return ['any'];
  }

  const withoutAny = current.filter((item) => item !== 'any');
  const isSelected = withoutAny.includes(protein);

  if (isSelected) {
    const next = withoutAny.filter((item) => item !== protein);
    return next;
  }

  return [...withoutAny, protein];
}

function toggleMealType(
  current: MealType[],
  mealType: MealType,
): { next: MealType[]; blocked: boolean } {
  const isSelected = current.includes(mealType);

  if (isSelected && current.length === 1) {
    return { next: current, blocked: true };
  }

  if (isSelected) {
    return { next: current.filter((type) => type !== mealType), blocked: false };
  }

  return { next: [...current, mealType], blocked: false };
}

function clampBudget(value: number): number {
  return Math.min(PROFILE_BUDGET.max, Math.max(PROFILE_BUDGET.min, value));
}

export const ProfileForm: FC<ProfileFormProps> = ({
  value,
  onChange,
  disabled = false,
  fieldErrors = {},
}) => {
  const [mealTypeHint, setMealTypeHint] = useState<string | null>(null);
  const update = (patch: Partial<Profile>) => onChange({ ...value, ...patch });

  const handleBudgetInput = (raw: string) => {
    const parsed = Number(raw);
    if (!Number.isInteger(parsed)) return;
    update({ budget: clampBudget(parsed) });
  };

  const handleMealTypeToggle = (mealType: MealType) => {
    const { next, blocked } = toggleMealType(value.meal_types, mealType);

    if (blocked) {
      setMealTypeHint('Нужно выбрать хотя бы один приём пищи.');
      return;
    }

    setMealTypeHint(null);
    update({
      meal_types: next,
      meals_per_day: next.length,
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <Section title="Имя" description="Как к вам обращаться в приложении.">
        <Input
          value={value.first_name}
          onChange={(event) => update({ first_name: event.target.value })}
          placeholder="Ваше имя"
          disabled={disabled}
          autoComplete="given-name"
        />
      </Section>

      <Section title="Цель питания" description="Выберите основной стиль меню.">
        <div className="grid grid-cols-2 gap-2">
          {GOAL_OPTIONS.map((option) => {
            const isActive = value.goal === option.value;

            return (
              <Card
                key={option.value}
                role="button"
                tabIndex={disabled ? -1 : 0}
                aria-pressed={isActive}
                onClick={() => !disabled && update({ goal: option.value as ProfileGoal })}
                onKeyDown={(event) => {
                  if (disabled) return;
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    update({ goal: option.value as ProfileGoal });
                  }
                }}
                className={cn(
                  'cursor-pointer transition-all',
                  isActive && 'ring-2 ring-app-link ring-offset-2 ring-offset-app-bg',
                  disabled && 'pointer-events-none opacity-50',
                )}
              >
                <CardContent className="flex flex-col gap-1 p-3">
                  {option.description && (
                    <Typography variant="h3" className="text-lg">
                      {option.description}
                    </Typography>
                  )}
                  <Typography variant="label">{option.label}</Typography>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </Section>

      <Section
        title="Основные продукты"
        description="Выберите продукты, которые хотите чаще видеть в меню."
      >
        <div className="flex flex-wrap gap-2">
          {PROTEIN_OPTIONS.map((option) => (
            <Chip
              key={option.value}
              selected={value.proteins.includes(option.value)}
              disabled={disabled}
              onClick={() => update({ proteins: toggleProtein(value.proteins, option.value) })}
            >
              {option.label}
            </Chip>
          ))}
        </div>
      </Section>

      <Section title="Бюджет на весь план" description="Сумма на весь период планирования.">
        <div className="flex flex-col gap-3">
          <input
            type="range"
            min={PROFILE_BUDGET.min}
            max={PROFILE_BUDGET.max}
            step={PROFILE_BUDGET.step}
            value={value.budget}
            disabled={disabled}
            onChange={(event) => update({ budget: Number(event.target.value) })}
            className="h-2 w-full cursor-pointer appearance-none rounded-full bg-app-bg accent-app-button disabled:opacity-50"
            aria-label="Бюджет на весь план"
          />
          <div className="flex items-center gap-2">
            <Input
              type="number"
              inputSize="md"
              min={PROFILE_BUDGET.min}
              max={PROFILE_BUDGET.max}
              step={1}
              value={value.budget}
              disabled={disabled}
              onChange={(event) => handleBudgetInput(event.target.value)}
              className="flex-1"
              aria-label="Бюджет на весь план в рублях"
            />
            <Typography variant="label" className="text-app-hint">
              ₽
            </Typography>
          </div>
        </div>
      </Section>

      <Section title="Период плана" description="На сколько дней планируем меню.">
        <div className="flex items-center justify-between gap-3">
          <Stepper
            value={value.days}
            min={PROFILE_DAYS.min}
            max={PROFILE_DAYS.max}
            disabled={disabled}
            onChange={(days) => update({ days })}
            aria-label="Период плана"
          />
          <Typography variant="caption" className="text-app-hint">
            1–7 дней
          </Typography>
        </div>
      </Section>

      <Section
        title="Приёмы пищи"
        description="Выберите, для каких приёмов пищи нужно составить меню."
      >
        <div className="flex flex-wrap gap-2">
          {MEAL_TYPE_OPTIONS.map((option) => (
            <Chip
              key={option.value}
              selected={value.meal_types.includes(option.value)}
              disabled={disabled}
              onClick={() => !disabled && handleMealTypeToggle(option.value)}
            >
              {option.label}
            </Chip>
          ))}
        </div>
        {mealTypeHint && (
          <Typography variant="caption" className="mt-2 text-app-hint" role="status">
            {mealTypeHint}
          </Typography>
        )}
      </Section>

      <Section title="Количество человек" description="Сколько человек будет есть из меню.">
        <Stepper
          value={value.persons}
          min={PROFILE_PERSONS.min}
          max={PROFILE_PERSONS.max}
          disabled={disabled}
          onChange={(persons) => update({ persons })}
          aria-label="Количество человек"
        />
      </Section>

      <Section
        title="Максимальное время активной готовки"
        description="Жёсткий лимит активного времени на одну готовку."
      >
        <SegmentedControl
          options={COOKTIME_OPTIONS}
          value={value.cooktime}
          disabled={disabled}
          onChange={(cooktime) => update({ cooktime: cooktime as ProfileCooktime })}
          aria-label="Максимальное время активной готовки"
        />
      </Section>

      <Section
        title="Выбирать более быстрые блюда"
        description="При прочих равных приложение будет чаще выбирать блюда, которые требуют меньше времени и действий."
      >
        <CookingSpeedPreferenceControl
          value={value.cooking_preferences}
          disabled={disabled}
          onChange={(cooking_preferences) => update({ cooking_preferences })}
        />
      </Section>

      <Section
        title="Предпочтение знакомых блюд"
        description="Мягкая настройка для следующих планов: при прочих равных выбирать более знакомые и предсказуемые блюда."
      >
        <FamiliarMealsPreferenceControl
          value={value.planning_preferences}
          disabled={disabled}
          onChange={(planning_preferences) => update({ planning_preferences })}
        />
      </Section>

      <DietaryConstraintsEditor
        profile={value}
        onChange={onChange}
        disabled={disabled}
        fieldErrors={fieldErrors}
      />

      <Section title="Магазин" description="Предпочитаемый магазин для расчёта корзины.">
        <div className="flex flex-wrap gap-2">
          {STORE_OPTIONS.map((option) => {
            const isActive = value.store === option.value;

            return (
              <Card
                key={option.value}
                role="button"
                tabIndex={disabled ? -1 : 0}
                aria-pressed={isActive}
                onClick={() => !disabled && update({ store: option.value })}
                onKeyDown={(event) => {
                  if (disabled) return;
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    update({ store: option.value });
                  }
                }}
                className={cn(
                  'cursor-pointer transition-all',
                  isActive && 'ring-2 ring-app-link ring-offset-2 ring-offset-app-bg',
                  disabled && 'pointer-events-none opacity-50',
                )}
              >
                <CardContent className="p-3">
                  <Typography variant="label">{option.label}</Typography>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </Section>
    </div>
  );
};
