import type { FC } from 'react';

import { Card, CardContent, Section, Typography } from '@/components/ui';
import { buildAppliedCookingSettingsViewModel } from '@/features/strategy/appliedCookingSettingsViewModel';
import { buildAppliedBehaviorSettingsLine } from '@/features/strategy/appliedBehaviorSettingsViewModel';
import { buildAppliedPlanningSettingsViewModel } from '@/features/strategy/appliedPlanningSettingsViewModel';
import { useStrategyById } from '@/hooks/useStrategyById';
import type {
  AppliedBehaviorSettings,
  AppliedCookingSettings,
  AppliedPlanningSettings,
} from '@/types/strategy';

interface AppliedPlanSettingsBlockProps {
  strategyId: string | null | undefined;
}

function parseAppliedCookingSettings(data: unknown): AppliedCookingSettings | null {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return null;
  }

  const appliedSettings = (data as Record<string, unknown>).applied_settings;
  if (!appliedSettings || typeof appliedSettings !== 'object' || Array.isArray(appliedSettings)) {
    return null;
  }

  const cooking = (appliedSettings as Record<string, unknown>).cooking;
  if (!cooking || typeof cooking !== 'object' || Array.isArray(cooking)) {
    return null;
  }

  const record = cooking as Record<string, unknown>;
  const cookingTimeLimit = record.cooking_time_limit;
  const preferFaster = record.prefer_faster_meals;
  const source = record.preference_source;

  if (
    typeof cookingTimeLimit !== 'number' ||
    typeof preferFaster !== 'boolean' ||
    (source !== 'profile' &&
      source !== 'memory' &&
      source !== 'default' &&
      source !== 'inferred')
  ) {
    return null;
  }

  return {
    cooking_time_limit: cookingTimeLimit,
    prefer_faster_meals: preferFaster,
    preference_source: source,
  };
}

function parseAppliedBehaviorSettings(data: unknown): AppliedBehaviorSettings | null {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return null;
  }

  const appliedSettings = (data as Record<string, unknown>).applied_settings;
  if (!appliedSettings || typeof appliedSettings !== 'object' || Array.isArray(appliedSettings)) {
    return null;
  }

  const behavior = (appliedSettings as Record<string, unknown>).behavior;
  if (!behavior || typeof behavior !== 'object' || Array.isArray(behavior)) {
    return null;
  }

  const record = behavior as Record<string, unknown>;
  const appliedCount = record.applied_count;
  const ignoredCount = record.ignored_count;
  const availabilityApplied = record.availability_preferences_applied;

  if (
    typeof appliedCount !== 'number' ||
    typeof ignoredCount !== 'number' ||
    typeof availabilityApplied !== 'boolean'
  ) {
    return null;
  }

  return {
    applied_count: appliedCount,
    ignored_count: ignoredCount,
    availability_preferences_applied: availabilityApplied,
  };
}

function parseAppliedPlanningSettings(data: unknown): AppliedPlanningSettings | null {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return null;
  }

  const appliedSettings = (data as Record<string, unknown>).applied_settings;
  if (!appliedSettings || typeof appliedSettings !== 'object' || Array.isArray(appliedSettings)) {
    return null;
  }

  const planning = (appliedSettings as Record<string, unknown>).planning;
  if (!planning || typeof planning !== 'object' || Array.isArray(planning)) {
    return null;
  }

  const record = planning as Record<string, unknown>;
  const preferFamiliar = record.prefer_familiar_meals;
  const source = record.familiar_meals_source;

  if (
    typeof preferFamiliar !== 'boolean' ||
    (source !== 'profile' && source !== 'default' && source !== 'inferred')
  ) {
    return null;
  }

  return {
    prefer_familiar_meals: preferFamiliar,
    familiar_meals_source: source,
  };
}

export const AppliedPlanSettingsBlock: FC<AppliedPlanSettingsBlockProps> = ({ strategyId }) => {
  const { data, isLoading, error, isRefreshError } = useStrategyById(
    strategyId,
    Boolean(strategyId),
  );

  if (!strategyId || isLoading) {
    return null;
  }

  if (error && !isRefreshError) {
    return null;
  }

  const settings = parseAppliedCookingSettings(data);
  const behaviorSettings = parseAppliedBehaviorSettings(data);
  const planningSettings = parseAppliedPlanningSettings(data);
  if (!settings) {
    return null;
  }

  const viewModel = buildAppliedCookingSettingsViewModel(settings);
  const behaviorLine = buildAppliedBehaviorSettingsLine(behaviorSettings);
  const planningViewModel = planningSettings
    ? buildAppliedPlanningSettingsViewModel(planningSettings)
    : null;

  return (
    <Card>
      <CardContent className="pt-4">
        <Section title="Настройки этого плана">
          <div className="flex flex-col gap-1">
            <Typography variant="body">{viewModel.timeLimitLine}</Typography>
            <Typography variant="body">{viewModel.preferenceLine}</Typography>
            {planningViewModel && (
              <Typography variant="body">{planningViewModel.preferenceLine}</Typography>
            )}
            {behaviorLine && <Typography variant="body">{behaviorLine}</Typography>}
            {viewModel.sourceLine && (
              <Typography variant="caption" className="text-app-hint">
                {viewModel.sourceLine}
              </Typography>
            )}
            {planningViewModel?.sourceLine && (
              <Typography variant="caption" className="text-app-hint">
                {planningViewModel.sourceLine}
              </Typography>
            )}
          </div>
        </Section>
      </CardContent>
    </Card>
  );
};
