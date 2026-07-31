import { describe, expect, it } from 'vitest';

import appSource from '@/App.tsx?raw';
import routesSource from '@/constants/routes.ts?raw';
import navigationSource from '@/constants/navigation.ts?raw';
import apiSource from '@/api/trends.ts?raw';
import sectionSource from '@/features/trends/TrendsSection.tsx?raw';
import progressPageSource from '@/pages/ProgressPage.tsx?raw';
import profilePageSource from '@/pages/ProfilePage.tsx?raw';
import weekPageSource from '@/pages/WeekPage.tsx?raw';

describe('Progress page and TrendsSection source contract', () => {
  it('registers a standalone progress route', () => {
    expect(routesSource).toContain("PROGRESS: '/progress'");
    expect(routesSource).toContain('Мой прогресс');
    expect(appSource).toContain('ProgressPage');
    expect(appSource).toContain('ROUTES.PROGRESS');
  });

  it('is reachable from ProfilePage but not part of bottom navigation', () => {
    expect(profilePageSource).toContain('ROUTES.PROGRESS');
    expect(navigationSource).not.toContain('PROGRESS');
  });

  it('does not touch WeekPage', () => {
    expect(weekPageSource).not.toContain('trends');
    expect(weekPageSource).not.toContain('Trend');
  });

  it('normalizes API payloads instead of trusting them', () => {
    expect(apiSource).toContain('normalizeTrendSummary');
  });

  it('renders qualitative texts and accessible structure', () => {
    expect(sectionSource).toContain('Мой прогресс');
    expect(sectionSource).toContain('aria-label');
    expect(sectionSource).toContain('aria-busy');
    expect(sectionSource).toContain('role="alert"');
    expect(sectionSource).toContain('<ul');
    expect(sectionSource).toContain('<li');
  });

  it('does not reference internal identifiers', () => {
    for (const internal of [
      'strategy_id',
      'event_key',
      'memory_id',
      'recipe_id',
      'decision_context',
    ]) {
      expect(sectionSource).not.toContain(internal);
      expect(progressPageSource).not.toContain(internal);
    }
  });
});
