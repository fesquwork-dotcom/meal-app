import { Route, Routes } from 'react-router-dom';
import { AppBootstrap } from '@/app/AppBootstrap';
import { ROUTES } from '@/constants/routes';
import { isDiagnosticsEnabled } from '@/lib/runtimeConfig';
import { RootLayout } from '@/layouts';
import {
  BasketPage,
  DiagnosticsPage,
  HomePage,
  MenuHistoryDetailPage,
  MenuHistoryPage,
  ProfilePage,
  ProgressPage,
  RecipeDetailsPage,
  RecipesPage,
  WeekPage,
} from '@/pages';

export default function App() {
  return (
    <AppBootstrap>
      <Routes>
        <Route element={<RootLayout />}>
          <Route path={ROUTES.HOME} element={<HomePage />} />
          <Route path={ROUTES.WEEK} element={<WeekPage />} />
          <Route path={ROUTES.BASKET} element={<BasketPage />} />
          <Route path={ROUTES.RECIPES} element={<RecipesPage />} />
          <Route path={`${ROUTES.RECIPES}/:recipeIndex`} element={<RecipeDetailsPage />} />
          <Route path={ROUTES.PROFILE} element={<ProfilePage />} />
          <Route path={ROUTES.PROGRESS} element={<ProgressPage />} />
          <Route path={ROUTES.HISTORY} element={<MenuHistoryPage />} />
          <Route path={`${ROUTES.HISTORY}/:menuPlanId`} element={<MenuHistoryDetailPage />} />
          {isDiagnosticsEnabled() && (
            <Route path="/diagnostics" element={<DiagnosticsPage />} />
          )}
        </Route>
      </Routes>
    </AppBootstrap>
  );
}
