import { useNavigate } from 'react-router-dom';
import { useCallback, useEffect, useReducer, useRef, useState, type FC } from 'react';
import {
  Button,
  InlineError,
  Modal,
  Spinner,
  Typography,
} from '@/components/ui';
import { getProfile } from '@/api/profile';
import { previewStrategy, resolveStrategyConflict } from '@/api/strategyPreview';
import { useGenerateMenuSheet } from '@/features/menu-generator/GenerateMenuSheetContext';
import { useGenerationProgressMessages } from '@/features/menu-generator/useGenerationProgressMessages';
import {
  buildPreviewSummaryLines,
  generationPreviewReducer,
  INITIAL_GENERATION_PREVIEW_STATE,
  isPreviewTokenExpired,
} from '@/features/menu-generator/generationPreviewReducer';
import {
  COOKTIME_OPTIONS,
  GOAL_OPTIONS,
  PROTEIN_OPTIONS,
  STORE_OPTIONS,
} from '@/features/profile/constants';
import { useProfile } from '@/features/profile/ProfileProvider';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import {
  formatPlanStartDate,
  planStartDateToPreviewRequest,
} from '@/features/menu-plan/profileToRequest';
import { getStrategyInputInvalidationEffect } from '@/features/strategy-inputs/strategyInputInvalidation';
import { isPreviewStale } from '@/features/strategy-inputs/previewLifecycle';
import { useStrategyInputs } from '@/features/strategy-inputs/useStrategyInputs';
import {
  classifyStrategyWorkflowError,
  routeStaleWorkflowError,
  StrategyWorkflowErrorPanel,
} from '@/features/strategy-workflow';
import type { StrategyWorkflowError, WorkflowRetryAction } from '@/features/strategy-workflow/types';
import { ROUTES } from '@/constants/routes';
import { formatMealTypesLabel } from '@/types/meal';
import type { Profile } from '@/types/profile';
import type { ConflictResolutionAction, ConflictResolutionOption } from '@/types/strategyPreview';
import { DecisionExplanationBlock } from '@/features/strategy/DecisionExplanationBlock';

function formatExclusionsSummary(profile: Profile): string {
  const parts = [
    ...profile.dietary_constraints.map((item) => item.value),
    ...profile.legacy_constraints,
  ];
  return parts.length > 0 ? parts.join(', ') : 'нет';
}

function getGoalLabel(goal: Profile['goal']): string {
  return GOAL_OPTIONS.find((option) => option.value === goal)?.label ?? goal;
}

function getCooktimeLabel(cooktime: Profile['cooktime']): string {
  return COOKTIME_OPTIONS.find((option) => option.value === cooktime)?.label ?? cooktime;
}

function getProteinLabels(proteins: Profile['proteins']): string {
  if (proteins.length === 0) {
    return 'Не выбрано';
  }
  return proteins
    .map((protein) => PROTEIN_OPTIONS.find((option) => option.value === protein)?.label ?? protein)
    .join(', ');
}

function getStoreLabel(store: string): string {
  return STORE_OPTIONS.find((option) => option.value === store)?.label ?? store;
}

interface SummaryRowProps {
  label: string;
  value: string;
}

const SummaryRow: FC<SummaryRowProps> = ({ label, value }) => (
  <div className="flex flex-col gap-0.5 border-b border-app-secondary py-2 last:border-0">
    <Typography variant="caption" className="text-app-hint">
      {label}
    </Typography>
    <Typography variant="body">{value}</Typography>
  </div>
);

export const GenerateMenuSheet: FC = () => {
  const navigate = useNavigate();
  const { isOpen, closeSheet } = useGenerateMenuSheet();
  const {
    profile,
    hasProfileDraft,
    isProfileLoaded,
    error: profileError,
    reloadProfile,
    applyExternalProfileUpdate,
    saveProfileDraft,
    isSaving,
  } = useProfile();
  const {
    revision,
    lastChange,
    invalidationSeq,
    notifyStrategyInputsChanged,
    notifyPreviewBecameStale,
  } = useStrategyInputs();
  const {
    isGenerating,
    generationStage,
    generationError,
    generateWithPreviewToken,
    clearGenerationError,
  } = useMenuPlan();
  const [previewState, dispatchPreview] = useReducer(
    generationPreviewReducer,
    INITIAL_GENERATION_PREVIEW_STATE,
  );
  const [workflowError, setWorkflowError] = useState<StrategyWorkflowError | null>(null);
  const previewStateRef = useRef(previewState);
  previewStateRef.current = previewState;

  const isPreviewing = previewState.phase === 'previewing' || previewState.phase === 'saving';
  const isBusy = isGenerating || isPreviewing || isSaving;

  const progress = useGenerationProgressMessages(isGenerating, generationStage);

  useEffect(() => {
    if (invalidationSeq === 0 || !lastChange) {
      return;
    }
    const effect = getStrategyInputInvalidationEffect(lastChange.reason);
    if (!effect.invalidatePreview) {
      return;
    }
    const current = previewStateRef.current;

    if (lastChange.kind === 'input_changed') {
      if (
        current.preview != null ||
        current.phase === 'ready' ||
        current.phase === 'conflict' ||
        current.phase === 'generating'
      ) {
        // Already rebuilt for the current strategy-inputs revision.
        if (!isPreviewStale(current, revision)) {
          return;
        }
      } else if (current.phase !== 'stale' && current.phase !== 'expired') {
        // Empty idle/building — no user-facing stale surface yet.
        return;
      }
    } else if (
      current.preview == null &&
      current.phase !== 'stale' &&
      current.phase !== 'expired' &&
      current.phase !== 'ready' &&
      current.phase !== 'conflict' &&
      current.phase !== 'generating'
    ) {
      return;
    }

    dispatchPreview({
      type: 'strategy_inputs_changed',
      reason: lastChange.reason,
      messageKey: effect.messageKey,
    });
  }, [invalidationSeq, lastChange, revision]);

  // Invalidate when the calendar day rolls past a frozen plan_start_date on an open ready preview.
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    if (previewState.phase !== 'ready' && previewState.phase !== 'conflict') {
      return;
    }
    if (!previewState.planStartDate) {
      return;
    }
    const today = formatPlanStartDate();
    if (today !== previewState.planStartDate) {
      notifyStrategyInputsChanged('plan_start_date_changed');
    }
  }, [
    isOpen,
    previewState.phase,
    previewState.planStartDate,
    notifyStrategyInputsChanged,
  ]);

  const runPreview = useCallback(
    async (planStartDate: string, builtAtRevision: number = revision) => {
      setWorkflowError(null);
      dispatchPreview({ type: 'preview_start', planStartDate });
      try {
        const preview = await previewStrategy(planStartDateToPreviewRequest(planStartDate));
        dispatchPreview({
          type: 'preview_success',
          preview,
          strategyInputsRevision: builtAtRevision,
        });
      } catch (err: unknown) {
        const classified = classifyStrategyWorkflowError(err);
        const routed = routeStaleWorkflowError(classified, notifyPreviewBecameStale);
        if (routed.routed) {
          return;
        }
        setWorkflowError(classified);
        dispatchPreview({ type: 'preview_error', error: classified.message });
      }
    },
    [revision, notifyPreviewBecameStale],
  );

  const ensureProfileSaved = useCallback(async (): Promise<Profile | null> => {
    if (!profile) {
      return null;
    }

    if (!hasProfileDraft) {
      return profile;
    }

    dispatchPreview({ type: 'save_start' });
    const saved = await saveProfileDraft();
    if (!saved.ok || !profile) {
      dispatchPreview({
        type: 'preview_error',
        error: saved.ok === false ? saved.error.message : 'Не удалось сохранить настройки',
      });
      return null;
    }

    return saved.data.profile;
  }, [profile, hasProfileDraft, saveProfileDraft]);

  const handleStartPreview = async () => {
    if (!profile || isBusy) return;
    clearGenerationError();
    dispatchPreview({ type: 'reset' });

    const currentProfile = await ensureProfileSaved();
    if (!currentProfile) return;

    const planStartDate = formatPlanStartDate();
    await runPreview(planStartDate);
  };

  const handleConfirmGeneration = async () => {
    if (!profile || !previewState.preview?.preview_token || isBusy) return;

    if (isPreviewTokenExpired(previewState.preview.preview_expires_at)) {
      notifyPreviewBecameStale('preview_token_expired');
      return;
    }

    dispatchPreview({ type: 'generate_start' });
    clearGenerationError();
    setWorkflowError(null);
    const result = await generateWithPreviewToken(previewState.preview.preview_token);
    if (result.ok) {
      dispatchPreview({ type: 'reset' });
      closeSheet();
      navigate(ROUTES.WEEK);
      return;
    }

    const routed = routeStaleWorkflowError(result.error, notifyPreviewBecameStale);
    if (routed.routed) {
      return;
    }

    setWorkflowError(result.error);
    // Retryable generation keeps local preview token — backend has no single-use nonce.
    dispatchPreview({
      type: 'generate_error',
      error: result.error.message,
    });
  };

  const handleResolve = async (option: ConflictResolutionOption) => {
    if (!profile || !previewState.activeConflict || !previewState.preview?.preview_token || isBusy) {
      return;
    }
    if (previewState.activeConflict.code === 'TOO_MANY_MEMORY_EXCLUSIONS') {
      closeSheet();
      navigate(ROUTES.PROFILE);
      return;
    }
    if (option.action === 'continue_with_warning') {
      if (previewState.preview?.status === 'ready') {
        dispatchPreview({
          type: 'preview_success',
          preview: previewState.preview,
          strategyInputsRevision:
            previewState.previewBuiltAtRevision ?? revision,
        });
      } else {
        await runPreview(previewState.planStartDate ?? formatPlanStartDate());
      }
      return;
    }

    dispatchPreview({ type: 'resolve_start' });
    try {
      const result = await resolveStrategyConflict({
        preview_token: previewState.preview.preview_token,
        conflict_id: previewState.activeConflict.conflict_id,
        action: option.action as ConflictResolutionAction,
      });

      dispatchPreview({ type: 'resolution_success' });

      // Token is consumed; bump strategy-inputs revision for compare listeners.
      const invalidateEffect = notifyStrategyInputsChanged('conflict_resolved');
      const builtAtRevision = revision + (invalidateEffect.incrementsRevision ? 1 : 0);

      if (result.status === 'requires_input') {
        if (result.field === 'proteins') {
          dispatchPreview({ type: 'requires_input', field: 'proteins' });
          closeSheet();
          navigate(ROUTES.PROFILE);
          return;
        }
      }

      // Server-owned resolution may have changed the persisted Profile.
      // Apply through the central method; 'conflict_resolved' above stays
      // the single coordinator reason for this operation.
      if (result.profile_revision != null) {
        const loaded = await getProfile();
        applyExternalProfileUpdate(
          {
            profile: loaded.profile,
            revision: loaded.revision,
            updatedAt: loaded.profile.updated_at ?? null,
          },
          { source: 'generation' },
        );
      }

      await runPreview(previewState.planStartDate ?? formatPlanStartDate(), builtAtRevision);
    } catch (err: unknown) {
      const classified = classifyStrategyWorkflowError(err);
      const routed = routeStaleWorkflowError(classified, notifyPreviewBecameStale);
      if (routed.routed) {
        return;
      }
      setWorkflowError(classified);
      dispatchPreview({ type: 'preview_error', error: classified.message });
    }
  };

  const handleWorkflowAction = (action: WorkflowRetryAction) => {
    clearGenerationError();
    setWorkflowError(null);
    if (action === 'build_new_preview' || action === 'retry_same_request') {
      dispatchPreview({ type: 'reset' });
      void handleStartPreview();
      return;
    }
    if (action === 'open_profile' || action === 'reload_profile') {
      dispatchPreview({ type: 'reset' });
      closeSheet();
      navigate(ROUTES.PROFILE);
      return;
    }
    if (action === 'restart_app') {
      window.location.reload();
    }
  };

  const handleEditSettings = () => {
    if (isBusy) return;
    clearGenerationError();
    setWorkflowError(null);
    dispatchPreview({ type: 'reset' });
    closeSheet();
    navigate(ROUTES.PROFILE);
  };

  const handleClose = () => {
    if (isBusy) return;
    clearGenerationError();
    setWorkflowError(null);
    dispatchPreview({ type: 'reset' });
    closeSheet();
  };

  const previewLines = previewState.preview ? buildPreviewSummaryLines(previewState.preview) : [];
  const showSettingsSummary =
    previewState.phase === 'idle' ||
    previewState.phase === 'stale' ||
    previewState.phase === 'expired';
  const showReadyPreview = previewState.phase === 'ready';
  const showConflict = previewState.phase === 'conflict' && previewState.activeConflict;
  const displayedWorkflowError =
    workflowError ??
    generationError ??
    (previewState.error && previewState.phase !== 'stale' && previewState.phase !== 'expired'
      ? classifyStrategyWorkflowError(new Error(previewState.error))
      : null);
  const staleCoordinatorMessage =
    previewState.phase === 'stale' || previewState.phase === 'expired'
      ? previewState.error
      : null;

  return (
    <Modal open={isOpen} onClose={handleClose} title="Создать меню">
      {!isProfileLoaded && !profileError && (
        <div className="flex flex-col items-center gap-3 py-6" role="status" aria-live="polite">
          <Spinner size="lg" />
          <Typography variant="body" className="text-app-hint">
            Загружаем настройки профиля…
          </Typography>
        </div>
      )}

      {profileError && !profile && (
        <InlineError message={profileError.message} onRetry={() => void reloadProfile()}>
          <Button type="button" variant="ghost" className="mt-2" onClick={handleEditSettings}>
            Перейти в профиль
          </Button>
        </InlineError>
      )}

      {profile && (
        <div className="flex flex-col gap-4">
          {showSettingsSummary && (
            <>
              <Typography variant="body" className="text-app-hint">
                Проверьте настройки перед созданием меню.
              </Typography>
              <div className="rounded-app-lg bg-app-secondary p-3">
                <SummaryRow label="Дней" value={String(profile.days)} />
                <SummaryRow
                  label="Бюджет"
                  value={`${profile.budget.toLocaleString('ru-RU')} ₽`}
                />
                <SummaryRow label="Человек" value={String(profile.persons)} />
                <SummaryRow
                  label="Приёмы пищи"
                  value={formatMealTypesLabel(profile.meal_types)}
                />
                <SummaryRow label="Цель" value={getGoalLabel(profile.goal)} />
                <SummaryRow label="Основные продукты" value={getProteinLabels(profile.proteins)} />
                <SummaryRow label="Время готовки" value={getCooktimeLabel(profile.cooktime)} />
                <SummaryRow
                  label="Исключения"
                  value={formatExclusionsSummary(profile)}
                />
                <SummaryRow label="Магазин" value={getStoreLabel(profile.store)} />
              </div>
            </>
          )}

          {showReadyPreview && (
            <section aria-labelledby="preview-heading" className="rounded-app-lg bg-app-secondary p-4">
              <Typography id="preview-heading" variant="h3" className="mb-2">
                План на {previewState.preview?.strategy?.days ?? profile.days} дней
              </Typography>
              <ul className="flex list-disc flex-col gap-1 pl-5">
                {previewLines.map((line) => (
                  <li key={line}>
                    <Typography variant="body">{line}</Typography>
                  </li>
                ))}
              </ul>
              <div className="mt-4">
                <DecisionExplanationBlock
                  collection={previewState.preview?.decision_explanations}
                  compact
                />
              </div>
            </section>
          )}

          {showConflict && (
            <section
              aria-labelledby="conflict-heading"
              className="rounded-app-lg border border-app-warning/40 bg-app-secondary p-4"
              role="alertdialog"
              aria-modal="true"
            >
              <Typography id="conflict-heading" variant="h3" className="mb-2">
                {previewState.activeConflict?.title}
              </Typography>
              <Typography variant="body" className="mb-4 text-app-hint">
                {previewState.activeConflict?.description}
              </Typography>
              <div className="flex flex-col gap-2">
                {previewState.activeConflict?.options.map((option) => (
                  <Button
                    key={option.action}
                    type="button"
                    variant={option.action === 'continue_with_warning' ? 'secondary' : 'default'}
                    size="full"
                    disabled={isBusy}
                    onClick={() => void handleResolve(option)}
                  >
                    {option.label}
                  </Button>
                ))}
                {previewState.activeConflict?.code === 'TOO_MANY_MEMORY_EXCLUSIONS' && (
                  <Button type="button" variant="ghost" size="full" onClick={handleEditSettings}>
                    Открыть память
                  </Button>
                )}
              </div>
            </section>
          )}

          {(isPreviewing || isSaving) && (
            <div
              className="flex items-center gap-3 rounded-app-lg bg-app-secondary p-4"
              role="status"
              aria-live="polite"
            >
              <Spinner />
              <Typography variant="body" className="text-app-hint">
                {previewState.phase === 'saving' || isSaving
                  ? 'Сохраняем настройки…'
                  : 'Проверяем настройки…'}
              </Typography>
            </div>
          )}

          {isGenerating && (
            <div className="flex flex-col gap-3 rounded-app-lg bg-app-secondary p-4" role="status" aria-live="polite">
              <Typography variant="h3">Создаём ваше меню</Typography>
              <div className="flex items-center gap-3">
                <Spinner />
                <div className="flex min-w-0 flex-col gap-1">
                  <Typography variant="body" className="text-app-hint">
                    {progress.message}
                  </Typography>
                  <Typography variant="caption" className="text-app-hint">
                    {progress.supporting}
                  </Typography>
                </div>
              </div>
            </div>
          )}

          {previewState.phase === 'expired' && (
            <section aria-labelledby="expired-heading" className="rounded-app-lg bg-app-secondary p-4">
              <Typography id="expired-heading" variant="h3" className="mb-2">
                Срок проверки настроек истёк
              </Typography>
              <Typography variant="body" className="text-app-hint">
                Проверьте настройки ещё раз перед созданием меню.
              </Typography>
            </section>
          )}

          {staleCoordinatorMessage && !displayedWorkflowError && (
            <InlineError
              message={staleCoordinatorMessage}
              onRetry={() => {
                clearGenerationError();
                setWorkflowError(null);
                dispatchPreview({ type: 'reset' });
                void handleStartPreview();
              }}
              retryLabel="Проверить план ещё раз"
            />
          )}

          {displayedWorkflowError && (
            <StrategyWorkflowErrorPanel
              error={displayedWorkflowError}
              showRequestId={Boolean(displayedWorkflowError.requestId)}
              onAction={handleWorkflowAction}
              onDismiss={() => {
                setWorkflowError(null);
                clearGenerationError();
              }}
            />
          )}

          <div className="flex flex-col gap-2 pt-2">
            {showReadyPreview ? (
              <Button
                type="button"
                size="full"
                disabled={isBusy || !isProfileLoaded}
                onClick={() => void handleConfirmGeneration()}
              >
                {isGenerating ? 'Создаём меню…' : 'Создать меню'}
              </Button>
            ) : previewState.phase === 'expired' ? (
              <Button
                type="button"
                size="full"
                disabled={isBusy || !isProfileLoaded}
                onClick={() => void handleStartPreview()}
              >
                Проверить снова
              </Button>
            ) : (
              <Button
                type="button"
                size="full"
                disabled={isBusy || !isProfileLoaded || Boolean(showConflict)}
                onClick={() => void handleStartPreview()}
              >
                {isPreviewing || isSaving ? 'Проверяем настройки…' : 'Составить меню'}
              </Button>
            )}
            <Button
              type="button"
              variant="secondary"
              size="full"
              disabled={isBusy}
              onClick={handleEditSettings}
            >
              Изменить настройки
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="full"
              disabled={isBusy}
              onClick={handleClose}
            >
              Отмена
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};
