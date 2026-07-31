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
import { InvalidMenuPlanError } from '@/features/menu-plan/fetchMenuPlan';
import { coordinateGenerationSuccess } from '@/features/menu-plan/coordinateGenerationSuccess';
import type { MenuPlanContextValue } from '@/features/menu-plan/MenuPlanContext';
import { generateMenu } from '@/api/menu';
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
  const [generationError, setGenerationError] = useState<StrategyWorkflowError | null>(null);
  const isGeneratingRef = useRef(false);

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

  const generateWithPreviewToken = useCallback(
    async (previewToken: string): Promise<GenerateMenuWorkflowResult> => {
      if (isGeneratingRef.current) {
        const error = classifyStrategyWorkflowError(new Error('Generation already in progress'));
        setGenerationError(error);
        return { ok: false, error };
      }

      if (!profile) {
        const error = classifyStrategyWorkflowError(new Error('Профиль не загружен'));
        setGenerationError(error);
        return { ok: false, error };
      }

      isGeneratingRef.current = true;
      setIsGenerating(true);
      setGenerationError(null);

      try {
        const plan = await generateMenu({ preview_token: previewToken });

        if (!plan) {
          throw new InvalidMenuPlanError();
        }

        coordinateGenerationSuccess(plan, profile, {
          setMenuPlan,
          onProfileGenerationSuccess: onGenerationSuccess,
        });

        return { ok: true, menuPlan: plan };
      } catch (err: unknown) {
        if (import.meta.env.DEV) {
          console.error('[MenuPlanProvider] generate failed:', err);
        }

        const error =
          err instanceof InvalidMenuPlanError
            ? classifyStrategyWorkflowError(err)
            : classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(error);
        setGenerationError(error);
        return { ok: false, error };
      } finally {
        isGeneratingRef.current = false;
        setIsGenerating(false);
      }
    },
    [onGenerationSuccess, profile],
  );

  const value = useMemo<MenuPlanContextValue>(
    () => ({
      menuPlan,
      isMenuPlanHydrated,
      isGenerating,
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
