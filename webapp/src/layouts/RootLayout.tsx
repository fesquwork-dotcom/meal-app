import { Outlet } from 'react-router-dom';
import type { FC } from 'react';
import { BasketProvider, MenuPlanBasketSync } from '@/features/basket';
import { GenerateMenuSheet } from '@/features/menu-generator/GenerateMenuSheet';
import { GenerateMenuSheetProvider } from '@/features/menu-generator/GenerateMenuSheetContext';
import { MenuPlanProvider } from '@/features/menu-plan/MenuPlanProvider';
import { ReplaceMealSheet } from '@/features/menu-plan/ReplaceMealSheet';
import { ReplaceMealSheetProvider } from '@/features/menu-plan/ReplaceMealSheetContext';
import { ProfileProvider } from '@/features/profile/ProfileProvider';
import { StrategyInputsProvider } from '@/features/strategy-inputs/StrategyInputsProvider';
import { cn } from '@/lib/utils';
import { AppHeader } from '@/layouts/AppHeader';
import { BottomNavigation } from '@/layouts/BottomNavigation';
import { MainButtonSlot } from '@/layouts/MainButtonSlot';

export interface RootLayoutProps {
  className?: string;
}

export const RootLayout: FC<RootLayoutProps> = ({ className }) => (
  <StrategyInputsProvider>
    <ProfileProvider>
      <MenuPlanProvider>
        <BasketProvider>
          <MenuPlanBasketSync>
            <GenerateMenuSheetProvider>
              <ReplaceMealSheetProvider>
              <div
                className={cn(
                  'min-h-screen bg-app-bg text-app-text font-app',
                  'pt-[var(--tg-safe-area-top,0px)] pb-[var(--tg-safe-area-bottom,0px)]',
                  className,
                )}
              >
                <div className="mx-auto flex min-h-screen w-full max-w-lg flex-col">
                  <AppHeader />

                  <main className="flex-1 pb-32">
                    <Outlet />
                  </main>

                  <MainButtonSlot />
                  <BottomNavigation />
                </div>
                <GenerateMenuSheet />
                <ReplaceMealSheet />
              </div>
              </ReplaceMealSheetProvider>
            </GenerateMenuSheetProvider>
          </MenuPlanBasketSync>
        </BasketProvider>
      </MenuPlanProvider>
    </ProfileProvider>
  </StrategyInputsProvider>
);
