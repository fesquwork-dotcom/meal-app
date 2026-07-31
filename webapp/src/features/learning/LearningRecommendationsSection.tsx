import { useEffect, useRef, useState, type FC } from 'react';

import {
  acceptLearningRecommendation,
  dismissLearningRecommendation,
  getLearningRecommendations,
} from '@/api/learning';
import { saveProfile } from '@/api/profile';
import { Button, Card, CardContent, Modal, Section, Skeleton, Typography } from '@/components/ui';
import {
  applyLearningPatch,
  buildLearningCardViewModel,
} from '@/features/learning/learningViewModel';
import { useProfile } from '@/features/profile/ProfileProvider';
import { useStrategyInputs } from '@/features/strategy-inputs/useStrategyInputs';
import type { LearningRecommendation } from '@/types/learning';

const DIRTY_DRAFT_MESSAGE = 'Сначала сохраните изменения профиля.';

export const LearningRecommendationsSection: FC = () => {
  const {
    serverProfile,
    serverRevision,
    hasProfileDraft,
    applyExternalProfileUpdate,
  } = useProfile();
  const { notifyStrategyInputsChanged } = useStrategyInputs();
  const [recommendations, setRecommendations] = useState<LearningRecommendation[]>([]);
  const [selected, setSelected] = useState<LearningRecommendation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const refresh = async () => {
    const summary = await getLearningRecommendations();
    setRecommendations(summary.recommendations);
  };

  useEffect(() => {
    let active = true;
    void getLearningRecommendations()
      .then((summary) => {
        if (active) setRecommendations(summary.recommendations);
      })
      .catch(() => {
        if (active) setError('Не удалось загрузить рекомендации.');
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const closeDetails = () => {
    setSelected(null);
    window.setTimeout(() => triggerRef.current?.focus(), 0);
  };

  const dismiss = async (recommendation: LearningRecommendation) => {
    setPendingId(recommendation.recommendation_id);
    setError(null);
    try {
      await dismissLearningRecommendation(recommendation.recommendation_id);
      setRecommendations((current) =>
        current.filter(
          (item) => item.recommendation_id !== recommendation.recommendation_id,
        ),
      );
      setAnnouncement('Рекомендация скрыта.');
      if (selected?.recommendation_id === recommendation.recommendation_id) {
        closeDetails();
      }
    } catch {
      setError('Не удалось скрыть рекомендацию.');
    } finally {
      setPendingId(null);
    }
  };

  const apply = async (recommendation: LearningRecommendation) => {
    if (hasProfileDraft) {
      setError(DIRTY_DRAFT_MESSAGE);
      return;
    }
    if (!serverProfile) {
      setError('Профиль пока недоступен.');
      return;
    }
    setPendingId(recommendation.recommendation_id);
    setError(null);
    try {
      // Accept records the human decision but does not mutate Profile.
      const accepted = await acceptLearningRecommendation(
        recommendation.recommendation_id,
      );
      // Existing Profile PUT performs the actual CAS-protected update.
      const nextProfile = applyLearningPatch(
        serverProfile,
        accepted.recommended_profile_patch,
      );
      const saved = await saveProfile(nextProfile, serverRevision);
      applyExternalProfileUpdate(
        {
          profile: saved.profile,
          revision: saved.revision,
          updatedAt: saved.profile.updated_at ?? null,
        },
        { source: 'learning_recommendation' },
      );
      notifyStrategyInputsChanged('learning_recommendation_applied');
      setAnnouncement(
        'Настройка профиля обновлена. Она повлияет только на следующий план.',
      );
      closeDetails();
      await refresh();
    } catch {
      setError(
        'Не удалось применить настройку. Обновите профиль и попробуйте снова.',
      );
    } finally {
      setPendingId(null);
    }
  };

  if (!isLoading && recommendations.length === 0 && !error) {
    return null;
  }

  const selectedView = selected ? buildLearningCardViewModel(selected) : null;

  return (
    <Section
      title="Что можно улучшить"
      description="Рекомендации основаны на результатах завершённых планов. Ничего не меняется без вашего решения."
    >
      <div className="sr-only" aria-live="polite">
        {announcement}
      </div>
      {isLoading && (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-28 w-full" />
          <span className="sr-only">Загружаем рекомендации…</span>
        </div>
      )}
      {error && (
        <Typography variant="caption" className="text-app-warning" role="alert">
          {error}
        </Typography>
      )}
      <div className="flex flex-col gap-3">
        {recommendations.map((recommendation) => {
          const card = buildLearningCardViewModel(recommendation);
          const expanded =
            selected?.recommendation_id === recommendation.recommendation_id;
          const pending = pendingId === recommendation.recommendation_id;
          return (
            <Card key={card.id}>
              <CardContent className="flex flex-col gap-2 pt-4">
                <Typography variant="body">{card.title}</Typography>
                <Typography variant="caption" className="text-app-hint">
                  {card.summary}
                </Typography>
                <Typography variant="caption" className="text-app-hint">
                  Основано на результатах последнего завершённого плана.
                </Typography>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={pending}
                    aria-expanded={expanded}
                    onClick={(event) => {
                      triggerRef.current = event.currentTarget;
                      setError(null);
                      setSelected(recommendation);
                    }}
                  >
                    {card.actionLabel}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={pending}
                    onClick={() => void dismiss(recommendation)}
                  >
                    {card.dismissLabel}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Modal
        open={selected !== null}
        onClose={closeDetails}
        title={selectedView?.title ?? 'Рекомендация'}
        titleId="learning-recommendation-title"
      >
        {selected && selectedView && (
          <div className="flex flex-col gap-4">
            <div>
              <Typography variant="label">Почему появилась рекомендация</Typography>
              <Typography variant="body" className="text-app-hint">
                {selectedView.details.reason}
              </Typography>
            </div>
            <div>
              <Typography variant="label">Что изменится</Typography>
              <Typography variant="body" className="text-app-hint">
                {selectedView.details.expectedEffect}
              </Typography>
            </div>
            <div>
              <Typography variant="label">Что не изменится и как отменить</Typography>
              <Typography variant="body" className="text-app-hint">
                {selectedView.details.whatWillNotChange} Настройку можно вернуть в
                профиле в любой момент.
              </Typography>
            </div>
            {error && (
              <Typography variant="caption" className="text-app-warning" role="alert">
                {error}
              </Typography>
            )}
            <div className="flex flex-col gap-2 sm:flex-row-reverse">
              <Button
                type="button"
                size="full"
                disabled={pendingId === selected.recommendation_id}
                onClick={() => void apply(selected)}
              >
                {pendingId === selected.recommendation_id
                  ? 'Применяем…'
                  : 'Применить'}
              </Button>
              <Button
                type="button"
                size="full"
                variant="secondary"
                disabled={pendingId === selected.recommendation_id}
                onClick={closeDetails}
              >
                Отмена
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </Section>
  );
};
