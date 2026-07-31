import { useRef, useState, type FC } from 'react';

import { Button, Card, CardContent, ConfirmDialog, Section, Skeleton, Typography } from '@/components/ui';
import {
  buildBehaviorInsightsViewModel,
  RECOMMENDATION_APPLIED_LABEL,
  SNOOZE_DURATION_OPTIONS,
} from '@/features/behavior/behaviorInsightsViewModel';
import { useProfile } from '@/features/profile/ProfileProvider';
import { useStrategyInputs } from '@/features/strategy-inputs/useStrategyInputs';
import { StrategyWorkflowErrorPanel } from '@/features/strategy-workflow/StrategyWorkflowErrorPanel';
import { useBehaviorInsights } from '@/hooks/useBehaviorInsights';
import type { BehaviorSnoozeDuration } from '@/types/behavior';

const DIRTY_DRAFT_MESSAGE = 'Сначала сохраните изменения профиля.';

function BehaviorInsightsSkeleton() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      <span className="sr-only">Загружаем наблюдения…</span>
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

interface BehaviorInsightCardProps {
  card: ReturnType<typeof buildBehaviorInsightsViewModel>['candidates'][number];
  isPending: boolean;
  actionError?: import('@/features/strategy-workflow/types').StrategyWorkflowError | null;
  onClearActionError?: () => void;
  onConfirm?: () => void;
  onDismiss?: () => void;
  onSnoozeRequest?: () => void;
  onApplyRecommendation?: () => void;
  onRevokeRequest?: () => void;
  emphasized?: boolean;
}

const BehaviorInsightCard: FC<BehaviorInsightCardProps> = ({
  card,
  isPending,
  actionError,
  onClearActionError,
  onConfirm,
  onDismiss,
  onSnoozeRequest,
  onApplyRecommendation,
  onRevokeRequest,
  emphasized = false,
}) => (
  <Card className={emphasized ? 'border border-app-accent/30 bg-app-secondary/40' : undefined}>
    <CardContent className="flex flex-col gap-2 pt-4">
      <Typography variant="body">{card.title}</Typography>
      <Typography variant="caption" className="text-app-hint">
        {card.description}
      </Typography>
      {card.evidenceLabel && (
        <Typography variant="caption" className="text-app-hint">
          {card.evidenceLabel}
        </Typography>
      )}
      <Typography
        variant="caption"
        className={emphasized ? 'text-app-accent' : 'text-app-hint'}
      >
        {card.statusLabel}
      </Typography>
      {card.recommendationPrompt && (
        <Typography variant="caption" className="text-app-hint">
          {card.recommendationPrompt}
        </Typography>
      )}
      {card.recommendationHint && (
        <Typography variant="caption" className="text-app-hint">
          {card.recommendationHint}
        </Typography>
      )}
      {card.recommendationApplied && (
        <Typography variant="caption" className="text-app-accent">
          {RECOMMENDATION_APPLIED_LABEL}
        </Typography>
      )}
      {actionError && (
        <StrategyWorkflowErrorPanel
          error={actionError}
          variant="inline"
          onDismiss={onClearActionError}
        />
      )}
      {(card.canConfirm ||
        card.canDismiss ||
        card.canSnooze ||
        card.canApplyRecommendation ||
        card.canRevoke) && (
        <div className="flex flex-wrap gap-2">
          {card.canConfirm && onConfirm && (
            <Button
              type="button"
              variant="secondary"
              disabled={isPending}
              aria-label={`Да, это похоже на меня: ${card.title}`}
              onClick={onConfirm}
            >
              {isPending ? 'Сохраняем…' : 'Да, это похоже на меня'}
            </Button>
          )}
          {card.canSnooze && onSnoozeRequest && (
            <Button
              type="button"
              variant="secondary"
              disabled={isPending}
              aria-label={`Не сейчас: ${card.title}`}
              onClick={onSnoozeRequest}
            >
              Не сейчас
            </Button>
          )}
          {card.canApplyRecommendation && onApplyRecommendation && (
            <Button
              type="button"
              variant="secondary"
              disabled={isPending}
              aria-label={card.recommendationActionLabel ?? 'Использовать более знакомые блюда'}
              onClick={onApplyRecommendation}
            >
              {isPending ? 'Сохраняем…' : card.recommendationActionLabel}
            </Button>
          )}
          {card.canRevoke && onRevokeRequest && (
            <Button
              type="button"
              variant="ghost"
              disabled={isPending}
              aria-label={`Отозвать подтверждение: ${card.title}`}
              onClick={onRevokeRequest}
            >
              Отозвать подтверждение
            </Button>
          )}
          {card.canDismiss && onDismiss && (
            <Button
              type="button"
              variant="ghost"
              disabled={isPending}
              aria-label={`Это не про меня: ${card.title}`}
              onClick={onDismiss}
            >
              Это не про меня
            </Button>
          )}
        </div>
      )}
    </CardContent>
  </Card>
);

export const BehaviorInsightsSection: FC = () => {
  const {
    status,
    insights,
    candidateCount,
    actionInsightId,
    loadError,
    actionErrorsByInsightId,
    isLoading,
    isRefreshing,
    isInitialLoadError,
    isRefreshError,
    retry,
    refresh,
    confirm,
    dismiss,
    snooze,
    revoke,
    applyRecommendation,
    clearActionError,
  } = useBehaviorInsights();
  const {
    hasProfileDraft,
    serverRevision,
    applyExternalProfileUpdate,
  } = useProfile();
  const { notifyStrategyInputsChanged } = useStrategyInputs();
  const [announcement, setAnnouncement] = useState('');
  const [dirtyDraftNotice, setDirtyDraftNotice] = useState<string | null>(null);
  const [snoozeInsightId, setSnoozeInsightId] = useState<string | null>(null);
  const [revokeCard, setRevokeCard] = useState<
    ReturnType<typeof buildBehaviorInsightsViewModel>['confirmed'][number] | null
  >(null);
  const sectionRef = useRef<HTMLDivElement>(null);
  const viewModel = buildBehaviorInsightsViewModel(insights, candidateCount);

  const sectionTitle = (
    <span className="inline-flex flex-wrap items-center gap-2">
      Что приложение заметило
      {candidateCount > 0 && (
        <span className="rounded-full bg-app-secondary px-2 py-0.5 text-sm text-app-accent">
          · {candidateCount}
        </span>
      )}
    </span>
  );

  const runApplyRecommendation = async (insightId: string) => {
    if (hasProfileDraft) {
      setDirtyDraftNotice(DIRTY_DRAFT_MESSAGE);
      return;
    }
    setDirtyDraftNotice(null);
    clearActionError();
    const result = await applyRecommendation(insightId, serverRevision);
    if (!result.ok) {
      return;
    }
    applyExternalProfileUpdate(
      {
        profile: result.data.profile,
        revision: result.data.revision,
        updatedAt: result.data.profile.updated_at ?? null,
      },
      { source: 'behavior_recommendation' },
    );
    notifyStrategyInputsChanged('behavior_recommendation_applied');
    setAnnouncement(RECOMMENDATION_APPLIED_LABEL);
  };

  const runSnooze = async (duration: BehaviorSnoozeDuration) => {
    if (!snoozeInsightId) return;
    const id = snoozeInsightId;
    setSnoozeInsightId(null);
    clearActionError();
    const result = await snooze(id, duration);
    if (result.ok) {
      notifyStrategyInputsChanged('behavior_snoozed');
      const label = duration === '7_days' ? '7 дней' : '30 дней';
      setAnnouncement(`Наблюдение отложено на ${label}.`);
      const nextFocus = sectionRef.current?.querySelector<HTMLElement>('button:not([disabled])');
      nextFocus?.focus();
    }
  };

  const runRevoke = async () => {
    if (!revokeCard) return;
    const card = revokeCard;
    setRevokeCard(null);
    clearActionError();
    const result = await revoke(card.id);
    if (result.ok) {
      notifyStrategyInputsChanged('behavior_revoked');
      setAnnouncement(
        result.data.profilePreferenceRemainsActive
          ? 'Наблюдение отозвано. Настройка в профиле сохранена.'
          : 'Подтверждение наблюдения отозвано.',
      );
    }
  };

  return (
    <Section
      title={sectionTitle}
      description="Приложение анализирует только ваши действия внутри меню и предлагает наблюдения для подтверждения. Ничего не применяется автоматически. Подтверждённые наблюдения о доступности продуктов учитываются при создании следующего плана."
    >
      <div ref={sectionRef}>
      <div className="sr-only" aria-live="polite">
        {announcement}
      </div>

      {isLoading && <BehaviorInsightsSkeleton />}

      {isInitialLoadError && loadError && (
        <StrategyWorkflowErrorPanel
          error={loadError}
          variant="compact"
          onRetry={retry.enabled ? () => void refresh() : undefined}
        />
      )}

      {(status === 'ready' || status === 'refreshing' || isRefreshError) && (
        <div className="flex flex-col gap-4" aria-live="polite">
          {hasProfileDraft && (
            <Typography variant="caption" className="text-app-hint">
              {DIRTY_DRAFT_MESSAGE}
            </Typography>
          )}
          {dirtyDraftNotice && (
            <Typography variant="caption" className="text-app-hint" role="status">
              {dirtyDraftNotice}
            </Typography>
          )}
          {isRefreshing && (
            <Typography variant="caption" className="text-app-hint" aria-live="polite">
              Обновляем данные…
            </Typography>
          )}
          {isRefreshError && loadError && (
            <div className="flex flex-col gap-1" role="status">
              <StrategyWorkflowErrorPanel
                error={loadError}
                variant="compact"
                onRetry={retry.enabled ? () => void refresh() : undefined}
              />
              <Typography variant="caption" className="text-app-hint">
                Не удалось обновить данные. Показана ранее загруженная версия.
              </Typography>
            </div>
          )}

          {!viewModel.hasAny && (
            <Card>
              <CardContent className="pt-4">
                <Typography variant="body">Пока новых наблюдений нет.</Typography>
                <Typography variant="caption" className="mt-2 text-app-hint">
                  Со временем приложение сможет заметить повторяющиеся действия, например
                  частые замены рецептов.
                </Typography>
              </CardContent>
            </Card>
          )}

          {viewModel.hasCandidates && (
            <div className="flex flex-col gap-2">
              <Typography variant="h3" as="h3" className="text-base">
                Новые наблюдения
              </Typography>
              <ul className="flex flex-col gap-2">
                {viewModel.candidates.map((card) => (
                  <li key={card.id}>
                    <BehaviorInsightCard
                      card={card}
                      emphasized
                      isPending={actionInsightId === card.id}
                      actionError={actionErrorsByInsightId[card.id] ?? null}
                      onClearActionError={() => clearActionError(card.id)}
                      onConfirm={() => {
                        clearActionError(card.id);
                        void confirm(card.id).then((result) => {
                          if (result.ok) {
                            notifyStrategyInputsChanged('behavior_confirmed');
                            setAnnouncement('Наблюдение подтверждено вами.');
                          }
                        });
                      }}
                      onSnoozeRequest={() => {
                        clearActionError(card.id);
                        setSnoozeInsightId(card.id);
                      }}
                      onDismiss={() => {
                        clearActionError(card.id);
                        void dismiss(card.id).then((result) => {
                          if (result.ok) {
                            notifyStrategyInputsChanged('behavior_candidate_dismissed');
                            setAnnouncement('Наблюдение скрыто.');
                            const nextFocus = sectionRef.current?.querySelector<HTMLElement>(
                              'button:not([disabled])',
                            );
                            nextFocus?.focus();
                          }
                        });
                      }}
                    />
                  </li>
                ))}
              </ul>
            </div>
          )}

          {viewModel.hasConfirmed && (
            <div className="flex flex-col gap-2">
              <Typography variant="h3" as="h3" className="text-base text-app-hint">
                Подтверждённые наблюдения
              </Typography>
              <ul className="flex flex-col gap-2">
                {viewModel.confirmed.map((card) => (
                  <li key={card.id}>
                    <BehaviorInsightCard
                      card={card}
                      isPending={actionInsightId === card.id}
                      actionError={actionErrorsByInsightId[card.id] ?? null}
                      onClearActionError={() => clearActionError(card.id)}
                      onApplyRecommendation={
                        card.canApplyRecommendation
                          ? () => void runApplyRecommendation(card.id)
                          : undefined
                      }
                      onRevokeRequest={
                        card.canRevoke ? () => setRevokeCard(card) : undefined
                      }
                    />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      </div>

      {snoozeInsightId && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4"
          onClick={() => setSnoozeInsightId(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Отложить наблюдение"
            className="w-full max-w-lg rounded-t-app-lg bg-app-bg p-4 shadow-lg sm:rounded-app-lg"
            onClick={(event) => event.stopPropagation()}
          >
            <Typography variant="h3" as="h3" className="text-base">
              Когда напомнить?
            </Typography>
            <div
              role="radiogroup"
              aria-label="Срок отложения"
              className="mt-3 flex flex-col gap-2"
            >
              {SNOOZE_DURATION_OPTIONS.map((option) => (
                <Button
                  key={option.value}
                  type="button"
                  variant="secondary"
                  disabled={actionInsightId === snoozeInsightId}
                  onClick={() => void runSnooze(option.value)}
                >
                  {option.label}
                </Button>
              ))}
              <Button type="button" variant="ghost" onClick={() => setSnoozeInsightId(null)}>
                Отмена
              </Button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(revokeCard)}
        title={revokeCard?.revokeConfirmTitle ?? ''}
        description={revokeCard?.revokeConfirmDescription ?? ''}
        confirmLabel="Отозвать"
        cancelLabel="Отмена"
        onConfirm={() => void runRevoke()}
        onCancel={() => setRevokeCard(null)}
      />
    </Section>
  );
};
