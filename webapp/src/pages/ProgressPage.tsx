import type { FC } from 'react';

import { InsightsSection } from '@/features/insights/InsightsSection';
import { TrendsSection } from '@/features/trends/TrendsSection';

/**
 * Sprint 7.1 — standalone «Мой прогресс» page.
 * Shows long-term trends across finalized weekly plans. Read-only:
 * nothing here influences decisions, learning, or the current plan.
 */
export const ProgressPage: FC = () => (
  <div className="flex flex-col gap-6 p-4 pb-8">
    <InsightsSection />
    <TrendsSection />
  </div>
);
