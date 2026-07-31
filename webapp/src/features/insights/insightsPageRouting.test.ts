import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

function read(path: string): string {
  return readFileSync(resolve(__dirname, path), 'utf-8');
}

const progressSource = read('../../pages/ProgressPage.tsx');
const appSource = read('../../App.tsx');
const sectionSource = read('./InsightsSection.tsx');

describe('Insight placement', () => {
  it('places insights inside the existing Progress product area', () => {
    expect(progressSource).toContain('<InsightsSection />');
    expect(progressSource).toContain('<TrendsSection />');
  });

  it('does not create a competing /insights route', () => {
    expect(appSource).not.toContain('/insights');
    expect(appSource).not.toContain('InsightsPage');
  });

  it('renders only confirmed cards and an honest empty state', () => {
    expect(sectionSource).toContain('viewModel.cards');
    expect(sectionSource).toContain('Пока недостаточно подтверждённых данных');
    expect(sectionSource).toContain('только результаты с достаточными доказательствами');
  });

  it('supports loading, retry, and screen-reader status', () => {
    expect(sectionSource).toContain('aria-busy');
    expect(sectionSource).toContain('role="alert"');
    expect(sectionSource).toContain('Повторить');
  });
});

