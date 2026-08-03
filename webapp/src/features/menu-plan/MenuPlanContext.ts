import type { MenuPlan } from '@/types/menu';
import type { GenerationJobStage } from '@/types/api';
import type { GenerateMenuWorkflowResult, StrategyWorkflowError } from '@/features/strategy-workflow/types';

export type { GenerateMenuWorkflowResult };

export interface MenuPlanContextValue {
  menuPlan: MenuPlan | null;
  isMenuPlanHydrated: boolean;
  isGenerating: boolean;
  /** Current async generation job stage when isGenerating; null otherwise. */
  generationStage: GenerationJobStage | null;
  generationError: StrategyWorkflowError | null;
  generateWithPreviewToken: (previewToken: string) => Promise<GenerateMenuWorkflowResult>;
  setMenuPlan: (plan: MenuPlan) => void;
  clearMenuPlan: () => void;
  clearGenerationError: () => void;
}
