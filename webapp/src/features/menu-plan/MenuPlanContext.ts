import type { MenuPlan } from '@/types/menu';
import type { GenerateMenuWorkflowResult, StrategyWorkflowError } from '@/features/strategy-workflow/types';

export type { GenerateMenuWorkflowResult };

export interface MenuPlanContextValue {
  menuPlan: MenuPlan | null;
  isMenuPlanHydrated: boolean;
  isGenerating: boolean;
  generationError: StrategyWorkflowError | null;
  generateWithPreviewToken: (previewToken: string) => Promise<GenerateMenuWorkflowResult>;
  setMenuPlan: (plan: MenuPlan) => void;
  clearMenuPlan: () => void;
  clearGenerationError: () => void;
}
