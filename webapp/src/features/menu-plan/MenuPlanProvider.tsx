import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FC,
  type ReactNode,
} from 'react';
import {
  createGenerationJob,
  getActiveGenerationJob,
} from '@/api/generationJobs';
import { getCurrentMenuPlan } from '@/api/menuPlan';
import { InvalidMenuPlanError } from '@/features/menu-plan/fetchMenuPlan';
import { coordinateGenerationSuccess } from '@/features/menu-plan/coordinateGenerationSuccess';
import type { MenuPlanContextValue } from '@/features/menu-plan/MenuPlanContext';
import {
  isAbortError,
  isGenerationJobInProgress,
  pollGenerationJob,
} from '@/features/menu-plan/pollGenerationJob';
import { reconcileMenuPlan } from '@/features/menu-plan/menuPlanSync';
import {
  clearPersistedMenuPlan,
  loadMenuPlanFromStorage,
  persistMenuPlan,
} from '@/features/menu-plan/menuPlanStorage';
import { useProfile } from '@/features/profile/ProfileProvider';
import {
  classifyStrategyWorkflowError,
  logWorkflowErrorClassified,
} from '@/features/strategy-workflow';
import type { GenerateMenuWorkflowResult, StrategyWorkflowError } from '@/features/strategy-workflow/types';
import type { GenerationJob, GenerationJobStage } from '@/types/api';
import type { MenuPlan } from '@/types/menu';

const MenuPlanContext = createContext<MenuPlanContextValue | null>(null);

export interface MenuPlanProviderProps {
  children: ReactNode;
}

export const MenuPlanProvider: FC<MenuPlanProviderProps> = ({ children }) => {
  const { profile, onGenerationSuccess } = useProfile();
  const [menuPlan, setMenuPlan] = useState<MenuPlan | null>(() => loadMenuPlanFromStorage());
  const [isMenuPlanHydrated, setIsMenuPlanHydrated] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStage, setGenerationStage] = useState<GenerationJobStage | null>(null);
  const [generationError, setGenerationError] = useState<StrategyWorkflowError | null>(null);
  const isGeneratingRef = useRef(false);
  const pollAbortRef = useRef<AbortController | null>(null);
  const profileRef = useRef(profile);
  profileRef.current = profile;
  const onGenerationSuccessRef = useRef(onGenerationSuccess);
  onGenerationSuccessRef.current = onGenerationSuccess;
  const resumeCheckedRef = useRef(false);
  const beginJobPollingRef = useRef<
    (jobId: string, stage?: GenerationJobStage | null) => Promise<GenerateMenuWorkflowResult>
  >(async () => ({
    ok: false,
    error: classifyStrategyWorkflowError(new Error('Generation not ready')),
  }));

  useEffect(() => {
    setIsMenuPlanHydrated(true);
  }, []);

  // Sprint 7.2 — one-time reconciliation with the durable server plan.
  // localStorage stays an offline cache; the backend is the source of truth.
  useEffect(() => {
    let active = true;
    void reconcileMenuPlan(loadMenuPlanFromStorage()).then((serverPlan) => {
      if (!active || !serverPlan || isGeneratingRef.current) {
        return;
      }
      setMenuPlan(serverPlan);
      persistMenuPlan(serverPlan);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    return () => {
      pollAbortRef.current?.abort();
      pollAbortRef.current = null;
    };
  }, []);

  const clearMenuPlan = useCallback(() => {
    setMenuPlan(null);
    clearPersistedMenuPlan();
  }, []);

  const clearGenerationError = useCallback(() => {
    setGenerationError(null);
  }, []);

  const updateMenuPlan = useCallback((plan: MenuPlan) => {
    setMenuPlan(plan);
  }, []);

  const finishGenerating = useCallback((abort: AbortController) => {
    if (pollAbortRef.current === abort) {
      pollAbortRef.current = null;
      isGeneratingRef.current = false;
      setIsGenerating(false);
      setGenerationStage(null);
    }
  }, []);

  const adoptSucceededPlan = useCallback(async (): Promise<MenuPlan> => {
    const plan = await getCurrentMenuPlan();
    if (!plan) {
      throw new InvalidMenuPlanError();
    }

    const currentProfile = profileRef.current;
    if (currentProfile) {
      coordinateGenerationSuccess(plan, currentProfile, {
        setMenuPlan,
        onProfileGenerationSuccess: onGenerationSuccessRef.current,
      });
    } else {
      setMenuPlan(plan);
      persistMenuPlan(plan);
    }

    return plan;
  }, []);

  const handleTerminalJob = useCallback(
    async (job: GenerationJob): Promise<GenerateMenuWorkflowResult> => {
      if (job.status === 'succeeded') {
        const plan = await adoptSucceededPlan();
        return { ok: true, menuPlan: plan };
      }

      const message = job.safe_message?.trim() || 'Не удалось создать меню';
      const classified = classifyStrategyWorkflowError(new Error(message));
      const error: StrategyWorkflowError = job.error_code
        ? { ...classified, code: job.error_code }
        : classified;
      logWorkflowErrorClassified(error);
      setGenerationError(error);
      return { ok: false, error };
    },
    [adoptSucceededPlan],
  );

  const pollJobToResult = useCallback(
    async (jobId: string, abort: AbortController): Promise<GenerateMenuWorkflowResult> => {
      try {
        const finalJob = await pollGenerationJob(jobId, {
          signal: abort.signal,
          onUpdate: (job) => {
            setGenerationStage(job.stage);
          },
        });

        if (abort.signal.aborted) {
          const error = classifyStrategyWorkflowError(new Error('Generation cancelled'));
          return { ok: false, error };
        }

        return await handleTerminalJob(finalJob);
      } catch (err: unknown) {
        if (isAbortError(err) || abort.signal.aborted) {
          const error = classifyStrategyWorkflowError(new Error('Generation cancelled'));
          return { ok: false, error };
        }

        if (import.meta.env.DEV) {
          console.error('[MenuPlanProvider] generation job failed:', err);
        }

        const error =
          err instanceof InvalidMenuPlanError
            ? classifyStrategyWorkflowError(err)
            : classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(error);
        setGenerationError(error);
        return { ok: false, error };
      } finally {
        finishGenerating(abort);
      }
    },
    [finishGenerating, handleTerminalJob],
  );

  const beginJobPolling = useCallback(
    async (jobId: string, stage?: GenerationJobStage | null): Promise<GenerateMenuWorkflowResult> => {
      const abort = new AbortController();
      pollAbortRef.current?.abort();
      pollAbortRef.current = abort;

      isGeneratingRef.current = true;
      setIsGenerating(true);
      setGenerationError(null);
      if (stage) {
        setGenerationStage(stage);
      }

      return pollJobToResult(jobId, abort);
    },
    [pollJobToResult],
  );
  beginJobPollingRef.current = beginJobPolling;

  // Sprint 10.6 — resume an in-flight server job after hydrate.
  useEffect(() => {
    if (!isMenuPlanHydrated || resumeCheckedRef.current) {
      return;
    }
    resumeCheckedRef.current = true;

    let cancelled = false;

    void (async () => {
      try {
        const job = await getActiveGenerationJob();
        if (cancelled) {
          // Strict Mode remount: allow the next effect to probe again.
          resumeCheckedRef.current = false;
          return;
        }
        if (!job || !isGenerationJobInProgress(job.status)) {
          return;
        }
        if (isGeneratingRef.current) {
          return;
        }
        await beginJobPollingRef.current(job.job_id, job.stage);
      } catch {
        if (cancelled) {
          resumeCheckedRef.current = false;
        }
        // Resume probe failures are non-fatal; user can start a new generation.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isMenuPlanHydrated]);

  const generateWithPreviewToken = useCallback(
    async (previewToken: string): Promise<GenerateMenuWorkflowResult> => {
      if (isGeneratingRef.current) {
        const error = classifyStrategyWorkflowError(new Error('Generation already in progress'));
        setGenerationError(error);
        return { ok: false, error };
      }

      if (!profileRef.current) {
        const error = classifyStrategyWorkflowError(new Error('Профиль не загружен'));
        setGenerationError(error);
        return { ok: false, error };
      }

      isGeneratingRef.current = true;
      setIsGenerating(true);
      setGenerationError(null);
      setGenerationStage('queued');

      try {
        const created = await createGenerationJob({ preview_token: previewToken });
        // 202 with a new or existing active job_id — poll whichever id we received.
        return await beginJobPolling(created.job_id, created.status === 'queued' ? 'queued' : null);
      } catch (err: unknown) {
        if (import.meta.env.DEV) {
          console.error('[MenuPlanProvider] create generation job failed:', err);
        }

        const error = classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(error);
        setGenerationError(error);
        isGeneratingRef.current = false;
        setIsGenerating(false);
        setGenerationStage(null);
        return { ok: false, error };
      }
    },
    [beginJobPolling],
  );

  const value = useMemo<MenuPlanContextValue>(
    () => ({
      menuPlan,
      isMenuPlanHydrated,
      isGenerating,
      generationStage,
      generationError,
      generateWithPreviewToken,
      setMenuPlan: updateMenuPlan,
      clearMenuPlan,
      clearGenerationError,
    }),
    [
      menuPlan,
      isMenuPlanHydrated,
      isGenerating,
      generationStage,
      generationError,
      generateWithPreviewToken,
      updateMenuPlan,
      clearMenuPlan,
      clearGenerationError,
    ],
  );

  return <MenuPlanContext.Provider value={value}>{children}</MenuPlanContext.Provider>;
};

export function useMenuPlan(): MenuPlanContextValue {
  const context = useContext(MenuPlanContext);

  if (!context) {
    throw new Error('useMenuPlan must be used within MenuPlanProvider');
  }

  return context;
}
