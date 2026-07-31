import { useCallback, useEffect, useId, useRef, useState, type FC } from 'react';

import { getLearnedPreferences } from '@/api/learnedPreferences';
import {
  Button,
  Card,
  CardContent,
  Section,
  Skeleton,
  Typography,
} from '@/components/ui';
import {
  REVIEW_BODY,
  REVIEW_TITLE,
} from '@/features/learned-preferences/learnedPreferenceEffectivenessViewModel';
import {
  keepLearnedPreferenceReview,
  logLearnedPreferenceReviewEvent,
  revokeFromLearnedPreferenceReview,
} from '@/features/learned-preferences/learnedPreferenceReviewWorkflow';
import {
  buildLearnedPreferencesViewModel,
  type LearnedPreferenceCardViewModel,
} from '@/features/learned-preferences/learnedPreferenceViewModel';
import {
  acceptPreference,
  revokePreference,
} from '@/features/learned-preferences/learnedPreferenceWorkflow';
import type { LearnedPreferencesResult } from '@/types/learnedPreferences';
import { useStrategyInputs } from '@/features/strategy-inputs/useStrategyInputs';

const LOAD_ERROR = 'Не удалось загрузить адаптивные предпочтения.';
const ACTION_ERROR = 'Не удалось обновить предпочтение. Попробуйте ещё раз.';

const EffectivenessBlock: FC<{
  card: LearnedPreferenceCardViewModel;
  showReview: boolean;
  isPending: boolean;
  onKeepReview: () => void;
  onRevokeReview: () => void;
}> = ({ card, showReview, isPending, onKeepReview, onRevokeReview }) => {
  const effectiveness = card.effectiveness;
  const detailsId = useId();
  const [open, setOpen] = useState(false);

  if (!effectiveness) return null;

  return (
    <div className="mt-1 flex flex-col gap-1.5">
      <Typography variant="caption" className="font-semibold text-app-hint">
        Как работает это предпочтение
      </Typography>
      <Typography variant="body" role="status">
        {effectiveness.title}
      </Typography>
      <Typography variant="caption" className="text-app-hint">
        {effectiveness.summary}
      </Typography>
      <Button
        type="button"
        variant="secondary"
        aria-expanded={open}
        aria-controls={detailsId}
        onClick={() => setOpen((value) => !value)}
      >
        Почему мы так считаем
      </Button>
      {open && (
        <div id={detailsId} className="flex flex-col gap-1">
          <Typography variant="caption" className="text-app-hint">
            {effectiveness.evidenceText}
          </Typography>
          {effectiveness.limitationTexts.map((text) => (
            <Typography
              key={text}
              variant="caption"
              className="text-app-hint"
            >
              {text}
            </Typography>
          ))}
        </div>
      )}
      {showReview && (
        <div
          className="mt-1 flex flex-col gap-2"
          role="region"
          aria-label={REVIEW_TITLE}
        >
          <Typography variant="body" className="font-semibold">
            {REVIEW_TITLE}
          </Typography>
          <Typography variant="caption" className="text-app-hint">
            {REVIEW_BODY}
          </Typography>
          <Button
            type="button"
            variant="secondary"
            disabled={isPending}
            aria-label={`Оставить включённым: ${card.title}`}
            onClick={onKeepReview}
          >
            {isPending ? 'Сохраняем…' : 'Оставить включённым'}
          </Button>
          <Button
            type="button"
            disabled={isPending}
            aria-label={`Отозвать после проверки: ${card.title}`}
            onClick={onRevokeReview}
          >
            {isPending ? 'Сохраняем…' : 'Отозвать'}
          </Button>
        </div>
      )}
    </div>
  );
};

const LearnedPreferenceCard: FC<{
  card: LearnedPreferenceCardViewModel;
  isPending: boolean;
  showReview: boolean;
  onAccept: () => void;
  onRevoke: () => void;
  onKeepReview: () => void;
  onRevokeReview: () => void;
}> = ({
  card,
  isPending,
  showReview,
  onAccept,
  onRevoke,
  onKeepReview,
  onRevokeReview,
}) => {
  const titleId = useId();
  const summaryId = useId();
  return (
    <Card>
      <CardContent
        className="flex flex-col gap-1.5 pt-4"
        role="article"
        aria-labelledby={titleId}
        aria-describedby={summaryId}
      >
        <Typography variant="body" className="font-semibold">
          <span id={titleId}>{card.title}</span>
        </Typography>
        <Typography variant="body" className="text-app-hint">
          <span id={summaryId}>{card.summary}</span>
        </Typography>
        <Typography variant="caption" className="text-app-hint">
          {card.confidenceLabel}
        </Typography>
        {card.status === 'active' && card.planningEffectLabel && (
          <Typography variant="caption" className="text-app-accent" role="status">
            {card.planningEffectLabel}
          </Typography>
        )}
        {card.status === 'active' && (
          <EffectivenessBlock
            card={card}
            showReview={showReview}
            isPending={isPending}
            onKeepReview={onKeepReview}
            onRevokeReview={onRevokeReview}
          />
        )}
        {card.status === 'candidate' && (
          <div className="mt-1 flex flex-col gap-2">
            <Button
              type="button"
              disabled={isPending}
              aria-label={`Использовать: ${card.title}`}
              onClick={onAccept}
            >
              {isPending ? 'Сохраняем…' : 'Использовать'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={isPending}
              aria-label={`Не использовать: ${card.title}`}
              onClick={onRevoke}
            >
              Не использовать
            </Button>
          </div>
        )}
        {card.status === 'active' && !showReview && (
          <Button
            type="button"
            variant="secondary"
            disabled={isPending}
            aria-label={`Отозвать: ${card.title}`}
            onClick={onRevoke}
          >
            {isPending ? 'Сохраняем…' : 'Отозвать'}
          </Button>
        )}
      </CardContent>
    </Card>
  );
};

export const LearnedPreferenceSection: FC = () => {
  const { notifyStrategyInputsChanged } = useStrategyInputs();
  const [result, setResult] = useState<LearnedPreferencesResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const loggedReviewIds = useRef<Set<string>>(new Set());

  const load = useCallback((withSpinner = true) => {
    if (withSpinner) setIsLoading(true);
    setError(null);
    return getLearnedPreferences()
      .then(setResult)
      .catch(() => setError(LOAD_ERROR))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    let active = true;
    getLearnedPreferences()
      .then((data) => {
        if (active) setResult(data);
      })
      .catch(() => {
        if (active) setError(LOAD_ERROR);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const runAction = useCallback(
    async (
      card: LearnedPreferenceCardViewModel,
      action: (id: string) => ReturnType<typeof acceptPreference>,
      options: { notifyCoordinator: boolean },
    ) => {
      setPendingId(card.id);
      setActionError(null);
      const outcome = await action(card.id);
      setPendingId(null);
      if (outcome.ok) {
        if (options.notifyCoordinator) {
          notifyStrategyInputsChanged(
            outcome.data.action === 'accept'
              ? 'learned_preference_accepted'
              : 'learned_preference_revoked',
          );
        }
        await load(false);
      } else {
        setActionError(ACTION_ERROR);
      }
    },
    [load, notifyStrategyInputsChanged],
  );

  const runKeepReview = useCallback(
    async (card: LearnedPreferenceCardViewModel) => {
      setPendingId(card.id);
      setActionError(null);
      const outcome = await keepLearnedPreferenceReview(card.id);
      setPendingId(null);
      if (outcome.ok) {
        // Dismiss review must not invalidate Preview or Compare.
        await load(false);
      } else {
        setActionError(ACTION_ERROR);
      }
    },
    [load],
  );

  const viewModel = buildLearnedPreferencesViewModel(result);

  useEffect(() => {
    if (!viewModel) return;
    for (const card of viewModel.cards) {
      if (
        card.effectiveness?.showReview === true &&
        !loggedReviewIds.current.has(card.id)
      ) {
        loggedReviewIds.current.add(card.id);
        logLearnedPreferenceReviewEvent('learned_preference_review_shown', {
          status: card.effectiveness.status,
          confidence: card.effectiveness.confidence,
          generation: card.effectiveness.generation,
        });
      }
    }
  }, [viewModel]);

  return (
    <Section
      title="Адаптивные предпочтения"
      description="Подтверждённые системой наблюдения, которые вы можете добровольно принять. Они не меняют профиль."
    >
      {isLoading && (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-28 w-full" />
          <span className="sr-only">Загружаем адаптивные предпочтения…</span>
        </div>
      )}
      {!isLoading && error && (
        <div className="flex flex-col gap-2" role="alert">
          <Typography variant="caption" className="text-app-warning">
            {error}
          </Typography>
          <Button type="button" variant="secondary" onClick={() => void load()}>
            Повторить
          </Button>
        </div>
      )}
      {!isLoading && !error && actionError && (
        <Typography variant="caption" className="text-app-warning" role="alert">
          {actionError}
        </Typography>
      )}
      {!isLoading && !error && viewModel && viewModel.cards.length > 0 && (
        <ul
          className="flex list-none flex-col gap-3 p-0"
          aria-label="Адаптивные предпочтения"
        >
          {viewModel.cards.map((card) => {
            const showReview = card.effectiveness?.showReview === true;
            return (
              <li key={card.id}>
                <LearnedPreferenceCard
                  card={card}
                  isPending={pendingId === card.id}
                  showReview={showReview}
                  onAccept={() =>
                    void runAction(card, acceptPreference, {
                      notifyCoordinator: true,
                    })
                  }
                  onRevoke={() =>
                    void runAction(card, revokePreference, {
                      notifyCoordinator: true,
                    })
                  }
                  onKeepReview={() => void runKeepReview(card)}
                  onRevokeReview={() =>
                    void runAction(card, revokeFromLearnedPreferenceReview, {
                      notifyCoordinator: true,
                    })
                  }
                />
              </li>
            );
          })}
        </ul>
      )}
      {!isLoading && !error && (!viewModel || viewModel.cards.length === 0) && (
        <Typography variant="body" className="text-app-hint">
          Пока нет адаптивных предпочтений. Они появятся, когда система накопит
          достаточно подтверждённого опыта.
        </Typography>
      )}
    </Section>
  );
};
