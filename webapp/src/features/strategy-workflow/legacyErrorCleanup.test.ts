import { describe, expect, it } from 'vitest';

import apiErrorSource from '@/lib/apiError.ts?raw';
import menuPlanContextSource from '@/features/menu-plan/MenuPlanContext.ts?raw';

describe('strategy workflow cleanup', () => {
  it('does not keep parallel CODE_MESSAGES registry in apiError', () => {
    expect(apiErrorSource).not.toContain('const CODE_MESSAGES');
  });

  it('does not expose GenerateMenuResult boolean-shaped alias', () => {
    expect(menuPlanContextSource).not.toContain('GenerateMenuResult');
    expect(menuPlanContextSource).toContain('GenerateMenuWorkflowResult');
  });
});
