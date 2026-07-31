import { describe, expect, it } from 'vitest';

import cardSource from '@/features/home/HomeStrategyContextCard.tsx?raw';
import viewModelSource from '@/features/home/homeStrategyContextViewModel.ts?raw';
import homePageSource from '@/pages/HomePage.tsx?raw';

describe('HomeStrategyContextCard (source smoke)', () => {
  it('renders nothing when the view model is hidden', () => {
    expect(cardSource).toContain('if (!viewModel.visible)');
    expect(cardSource).toContain('return null');
  });

  it('offers navigation to the full explanation', () => {
    expect(cardSource).toContain('Подробнее о плане');
    expect(cardSource).toContain('onOpenDetails');
  });

  it('uses theme tokens, not destructive styling', () => {
    expect(cardSource).toContain('bg-app-secondary');
    expect(cardSource).not.toContain('destructive');
  });
});

describe('HomePage strategy context integration (source smoke)', () => {
  it('shows the metadata block only alongside an existing MenuPlan', () => {
    expect(homePageSource).toContain('menuPlan && strategyContext.visible');
  });

  it('routes the details action to WeekPage', () => {
    expect(homePageSource).toContain('onOpenDetails={() => navigate(ROUTES.WEEK)}');
  });

  it('keeps the MenuPlan/Strategy boundary: strategy data never replaces the menu', () => {
    expect(homePageSource).not.toContain('clearMenuPlan');
    expect(viewModelSource).not.toContain('menuPlanStorage');
    expect(viewModelSource).not.toContain('localStorage');
    expect(viewModelSource).not.toContain('STORAGE_KEYS');
  });
});
