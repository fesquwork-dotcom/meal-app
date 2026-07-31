import { useEffect, useRef, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  CardContent,
  ConfirmDialog,
  Section,
  Skeleton,
  Typography,
} from '@/components/ui';
import { ROUTES } from '@/constants/routes';
import { useBasketState } from '@/features/basket/useBasketState';
import { MemorySignalsSection } from '@/features/memory/MemorySignalsSection';
import { BehaviorInsightsSection } from '@/features/behavior/BehaviorInsightsSection';
import { LearnedPreferenceSection } from '@/features/learned-preferences/LearnedPreferenceSection';
import { LearningRecommendationsSection } from '@/features/learning/LearningRecommendationsSection';
import { ProfileForm } from '@/features/profile/ProfileForm';
import { extractProfileDraft, isCookingPreferenceDirty } from '@/features/profile/profileDraft';
import { buildNextPlanCookingHint } from '@/features/strategy/appliedCookingSettingsViewModel';
import { ProfileConflictDialog } from '@/features/profile/ProfileConflictDialog';
import { ProfileServerUpdateBanner } from '@/features/profile/ProfileServerUpdateBanner';
import { useProfile } from '@/features/profile/ProfileProvider';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import { formatPlanStartDate } from '@/features/menu-plan/profileToRequest';
import { StrategyCompareSection } from '@/features/strategy/StrategyCompareSection';
import { useStrategyInputs } from '@/features/strategy-inputs/useStrategyInputs';
import {
  StrategyWorkflowErrorPanel,
  routeStaleWorkflowError,
} from '@/features/strategy-workflow';

function ProfileFormSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true">
      <span className="sr-only">Загружаем настройки профиля…</span>
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="flex flex-col gap-3">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-11 w-full" />
        </div>
      ))}
    </div>
  );
}

export const ProfilePage: FC = () => {
  const navigate = useNavigate();
  const { clearMenuPlan, menuPlan, generateWithPreviewToken, isGenerating } = useMenuPlan();
  const { notifyPreviewBecameStale } = useStrategyInputs();
  const { clearAll } = useBasketState();
  const {
    profile,
    serverProfile,
    updateProfile,
    hasProfileDraft,
    resetProfileDraft,
    saveProfileDraft,
    isLoading,
    isRefreshing,
    isSaving,
    saveError,
    error,
    isProfileLoaded,
    isRefreshError,
    retry,
    reloadProfile,
    ensureFreshProfile,
    conflict,
    rebasePending,
    reloadServerProfile,
    beginRebaseOverwrite,
    cancelRebaseOverwrite,
    serverUpdate,
    serverUpdateBannerDismissedForRevision,
    dismissServerUpdateBanner,
    loadServerProfileVersion,
  } = useProfile();
  const [isDeleteMenuDialogOpen, setIsDeleteMenuDialogOpen] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [serverVersionAnnouncement, setServerVersionAnnouncement] = useState('');
  const settingsHeadingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void ensureFreshProfile();
  }, [ensureFreshProfile]);

  if (isLoading && !isProfileLoaded && !profile) {
    return (
      <div className="p-4">
        <Section title="Профиль" description="Загружаем ваши настройки…">
          <ProfileFormSkeleton />
        </Section>
      </div>
    );
  }

  if (error && !isProfileLoaded && !profile) {
    return (
      <div className="p-4">
        <StrategyWorkflowErrorPanel
          error={error}
          variant="full"
          onRetry={() => void reloadProfile()}
        />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="p-4">
        <Card>
          <CardContent className="pt-4">
            <Typography variant="body" className="text-app-hint">
              Профиль недоступен. Попробуйте обновить страницу.
            </Typography>
            <Button type="button" className="mt-4" onClick={() => void reloadProfile()}>
              Повторить
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const handleDeleteMenu = () => {
    clearMenuPlan();
    setIsDeleteMenuDialogOpen(false);
    navigate('/');
  };

  const handleSave = async () => {
    setSaveSuccess(false);
    const saved = await saveProfileDraft();
    if (saved.ok) {
      setSaveSuccess(true);
    }
  };

  const handleKeepLocal = () => {
    beginRebaseOverwrite();
  };

  const handleLoadServerVersion = () => {
    loadServerProfileVersion();
    setServerVersionAnnouncement('Загружена сохранённая версия настроек.');
    settingsHeadingRef.current?.focus();
  };

  const proteinsIncomplete = profile.proteins.length === 0;
  const cookingPreferenceDirty =
    serverProfile !== null &&
    isCookingPreferenceDirty(serverProfile, extractProfileDraft(profile));

  return (
    <div className="flex flex-col gap-6 p-4 pb-8">
      <div ref={settingsHeadingRef} tabIndex={-1} className="flex flex-col gap-6 outline-none">
      <Section
        title="Настройки питания"
        description="Изменения будут применены к следующему плану."
      >
        {hasProfileDraft && (
          <Typography
            variant="caption"
            className="inline-flex w-fit rounded-full bg-app-secondary px-3 py-1 text-app-accent"
          >
            Есть несохранённые изменения
          </Typography>
        )}
        {proteinsIncomplete && (
          <Typography
            variant="caption"
            className="inline-flex w-fit rounded-full bg-app-warning/10 px-3 py-1 text-app-warning"
            role="status"
          >
            Выберите источник белка, чтобы создать меню
          </Typography>
        )}
        {cookingPreferenceDirty && (
          <Typography variant="caption" className="text-app-hint" role="status">
            {buildNextPlanCookingHint()}
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
              onRetry={retry.enabled ? () => void reloadProfile() : undefined}
            />
            <Typography variant="caption" className="text-app-hint">
              Не удалось обновить данные. Показана ранее загруженная версия.
            </Typography>
          </div>
        )}
        {!conflict && (
          <ProfileServerUpdateBanner
            state={serverUpdate}
            dismissedForRevision={serverUpdateBannerDismissedForRevision}
            onContinueEditing={dismissServerUpdateBanner}
            onLoadServerVersion={handleLoadServerVersion}
          />
        )}
        {serverVersionAnnouncement && (
          <Typography variant="caption" className="text-app-hint" role="status" aria-live="polite">
            {serverVersionAnnouncement}
          </Typography>
        )}
        <ProfileForm
          value={profile}
          onChange={(next) => {
            setSaveSuccess(false);
            setServerVersionAnnouncement('');
            updateProfile(next);
          }}
          disabled={isLoading || isSaving}
        />
        <div className="flex flex-col gap-2" aria-live="polite">
          <ProfileConflictDialog
            open={Boolean(conflict)}
            conflict={conflict}
            rebasePending={rebasePending}
            onReloadServer={() => {
              reloadServerProfile();
            }}
            onKeepLocal={handleKeepLocal}
            onConfirmRebase={() => void handleSave()}
            onCancelRebase={cancelRebaseOverwrite}
          />
          <Button
            type="button"
            size="full"
            disabled={(!hasProfileDraft && !rebasePending) || isSaving || isLoading || Boolean(conflict && !rebasePending)}
            onClick={() => void handleSave()}
          >
            {isSaving
              ? 'Сохраняем изменения…'
              : rebasePending
                ? 'Сохранить мои изменения'
                : 'Сохранить изменения'}
          </Button>
          {saveSuccess && (
            <Typography variant="caption" className="text-app-accent" role="status">
              Настройки сохранены
            </Typography>
          )}
          {saveError && (
            <StrategyWorkflowErrorPanel
              error={saveError}
              variant="inline"
            />
          )}
        </div>
      </Section>
      </div>

      <LearningRecommendationsSection />

      <Section
        title="Мой прогресс"
        description="Долгосрочные изменения по завершённым планам: замены, подтверждённые успехи и качество решений."
      >
        <Button
          type="button"
          variant="secondary"
          size="full"
          onClick={() => navigate(ROUTES.PROGRESS)}
        >
          Открыть прогресс
        </Button>
      </Section>

      <Section
        title="История планов"
        description="Прошлые недельные меню, сохранённые на сервере: исходный вариант и вариант после замен."
      >
        <Button
          type="button"
          variant="secondary"
          size="full"
          onClick={() => navigate(ROUTES.HISTORY)}
        >
          Открыть историю
        </Button>
      </Section>

        <MemorySignalsSection />

        <LearnedPreferenceSection />

        <BehaviorInsightsSection />

      <StrategyCompareSection
        strategyId={menuPlan?.strategy_id}
        planStartDate={menuPlan?.plan_start_date ?? formatPlanStartDate()}
        hasProfileDraft={hasProfileDraft}
        onGenerateWithToken={async (token) => {
          const result = await generateWithPreviewToken(token);
          if (result.ok) {
            navigate('/');
            return result;
          }
          routeStaleWorkflowError(result.error, notifyPreviewBecameStale);
          return result;
        }}
        isGenerating={isGenerating}
      />

      <Section title="Данные приложения" description="Управление локально сохранёнными данными.">
        <div className="flex flex-col gap-2">
          <Button type="button" variant="secondary" size="full" onClick={clearAll}>
            Очистить покупки
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="full"
            onClick={() => setIsDeleteMenuDialogOpen(true)}
          >
            Удалить сохранённое меню
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="full"
            disabled={!hasProfileDraft}
            onClick={resetProfileDraft}
          >
            Сбросить черновик настроек
          </Button>
        </div>
      </Section>

      <ConfirmDialog
        open={isDeleteMenuDialogOpen}
        title="Удалить сохранённое меню?"
        description="План питания будет удалён с устройства. Вы сможете создать новое меню в любой момент."
        confirmLabel="Удалить"
        cancelLabel="Отмена"
        onConfirm={handleDeleteMenu}
        onCancel={() => setIsDeleteMenuDialogOpen(false)}
      />
    </div>
  );
};
