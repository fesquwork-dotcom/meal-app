import { useState, type FC } from 'react';

import { Button, Card, CardContent, Section, Typography } from '@/components/ui';
import { buildMemorySignalsViewModel } from '@/features/memory/memorySignalsViewModel';
import { useProfile } from '@/features/profile/ProfileProvider';
import { StrategyWorkflowErrorPanel } from '@/features/strategy-workflow/StrategyWorkflowErrorPanel';
import { useStrategyInputs } from '@/features/strategy-inputs/useStrategyInputs';
import { useMemorySignals } from '@/hooks/useMemorySignals';

const DIRTY_DRAFT_MESSAGE = 'Сначала сохраните изменения профиля.';
const ALREADY_COVERED_MESSAGE = 'Этот продукт уже исключён в профиле.';
const LEGACY_CONVERTED_MESSAGE = 'Старое исключение перенесено в постоянные предпочтения.';

export const MemorySignalsSection: FC = () => {
  const {
    hasProfileDraft,
    serverProfile,
    serverRevision,
    applyExternalProfileUpdate,
  } = useProfile();
  const { notifyStrategyInputsChanged } = useStrategyInputs();
  const {
    signals,
    isLoading,
    error,
    isRefreshing,
    isRefreshError,
    actionErrorsBySignalId,
    promotionError,
    confirm,
    dismiss,
    promote,
    reload,
    retry,
    clearActionError,
  } = useMemorySignals();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  if (isLoading) {
    return null;
  }

  if (error && !isRefreshError) {
    return (
      <Section title="Приложение запомнило">
        <StrategyWorkflowErrorPanel
          error={error}
          variant="compact"
          onRetry={retry.enabled ? () => void reload() : undefined}
        />
      </Section>
    );
  }

  const viewModels = buildMemorySignalsViewModel(signals);
  if (viewModels.length === 0 && !error) {
    return null;
  }

  const runConfirm = async (id: string) => {
    setPendingId(id);
    clearActionError(id);
    setActionNotice(null);
    const result = await confirm(id);
    setPendingId(null);
    if (!result.ok) {
      return;
    }
    notifyStrategyInputsChanged('memory_confirmed');
  };

  const runDismiss = async (id: string) => {
    setPendingId(id);
    clearActionError(id);
    setActionNotice(null);
    const result = await dismiss(id);
    setPendingId(null);
    if (!result.ok) {
      return;
    }
    notifyStrategyInputsChanged(
      result.data.wasConfirmed ? 'memory_confirmed_dismissed' : 'memory_candidate_dismissed',
    );
  };

  const runPromote = async (id: string) => {
    if (hasProfileDraft) {
      setActionNotice(null);
      clearActionError(id);
      setPendingId(null);
      return;
    }

    setPendingId(id);
    clearActionError(id);
    setActionNotice(null);
    const hadLegacyBefore = (serverProfile?.legacy_constraints.length ?? 0) > 0;
    const result = await promote(id, serverRevision);
    setPendingId(null);
    if (!result.ok) {
      return;
    }
    applyExternalProfileUpdate(
      {
        profile: result.data.profile,
        revision: result.data.revision,
        updatedAt: result.data.profile.updated_at ?? null,
      },
      { source: 'memory_promotion' },
    );
    notifyStrategyInputsChanged('memory_promoted');
    await reload();
    if (result.data.promotionStatus === 'already_covered') {
      setActionNotice(ALREADY_COVERED_MESSAGE);
    } else if (
      result.data.promotionStatus === 'promoted' &&
      hadLegacyBefore &&
      result.data.profile.legacy_constraints.length === 0
    ) {
      setActionNotice(LEGACY_CONVERTED_MESSAGE);
    }
  };

  if (viewModels.length === 0) {
    return null;
  }

  return (
    <Section
      title="Приложение запомнило"
      description="Наблюдения на основе ваших замен. Вы можете подтвердить или удалить их."
    >
      {hasProfileDraft && (
        <Typography variant="caption" className="text-app-hint">
          {DIRTY_DRAFT_MESSAGE}
        </Typography>
      )}
      {isRefreshing && (
        <Typography variant="caption" className="text-app-hint" aria-live="polite">
          Обновляем данные…
        </Typography>
      )}
      {isRefreshError && error && (
        <div className="flex flex-col gap-1" role="status">
          <StrategyWorkflowErrorPanel
            error={error}
            variant="compact"
            onRetry={retry.enabled ? () => void reload() : undefined}
          />
          <Typography variant="caption" className="text-app-hint">
            Не удалось обновить данные. Показана ранее загруженная версия.
          </Typography>
        </div>
      )}
      {promotionError && (
        <StrategyWorkflowErrorPanel
          error={promotionError}
          variant="inline"
          onDismiss={() => clearActionError()}
        />
      )}
      {actionNotice && (
        <Typography variant="caption" className="text-app-accent">
          {actionNotice}
        </Typography>
      )}
      <ul className="flex flex-col gap-2">
        {viewModels.map((signal) => (
          <li key={signal.id}>
            <Card>
              <CardContent className="flex flex-col gap-2 pt-4">
                <Typography variant="body">{signal.title}</Typography>
                {signal.detail && (
                  <Typography variant="caption" className="text-app-hint">
                    {signal.detail}
                  </Typography>
                )}
                {signal.promotionHint && (
                  <Typography variant="caption" className="text-app-hint">
                    {signal.promotionHint}
                  </Typography>
                )}
                {signal.isConfirmed && (
                  <Typography variant="caption" className="text-app-accent">
                    Запомнено
                  </Typography>
                )}
                {actionErrorsBySignalId[signal.id] && (
                  <StrategyWorkflowErrorPanel
                    error={actionErrorsBySignalId[signal.id]!}
                    variant="inline"
                    onDismiss={() => clearActionError(signal.id)}
                  />
                )}
                <div className="flex flex-wrap gap-2">
                  {!signal.isConfirmed && (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={pendingId === signal.id}
                      onClick={() => void runConfirm(signal.id)}
                    >
                      Подтвердить
                    </Button>
                  )}
                  {signal.canPromote && (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={pendingId === signal.id || hasProfileDraft}
                      onClick={() => void runPromote(signal.id)}
                    >
                      {pendingId === signal.id ? 'Добавляем в профиль…' : 'Добавить в профиль'}
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={pendingId === signal.id}
                    onClick={() => void runDismiss(signal.id)}
                  >
                    Удалить
                  </Button>
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </Section>
  );
};
