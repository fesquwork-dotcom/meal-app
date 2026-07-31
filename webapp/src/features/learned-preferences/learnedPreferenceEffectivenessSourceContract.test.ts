import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const section = readFileSync(
  resolve(__dirname, './LearnedPreferenceSection.tsx'),
  'utf-8',
);
const viewModel = readFileSync(
  resolve(__dirname, './learnedPreferenceViewModel.ts'),
  'utf-8',
);
const review = readFileSync(
  resolve(__dirname, './learnedPreferenceReviewWorkflow.ts'),
  'utf-8',
);

describe('learnedPreferenceEffectivenessSourceContract', () => {
  it('shows effectiveness disclosure and review copy on Profile cards', () => {
    expect(section).toContain('Как работает это предпочтение');
    expect(section).toContain('Почему мы так считаем');
    expect(section).toContain('Оставить включённым');
    expect(section).toContain('aria-expanded');
  });

  it('persists keep via dismiss-review and revokes via existing workflow', () => {
    expect(section).toContain('keepLearnedPreferenceReview');
    expect(section).toContain('revokeFromLearnedPreferenceReview');
    expect(review).toContain('dismissLearnedPreferenceReview');
    expect(review).toContain('revokePreference');
    expect(section).not.toContain('dismissedReviews');
  });

  it('notifies coordinator only after accept/revoke, never after keep', () => {
    expect(section).toContain('notifyCoordinator: true');
    expect(section).toContain('runKeepReview');
    expect(section).toContain(
      '// Dismiss review must not invalidate Preview or Compare.',
    );
    expect(section.indexOf('if (outcome.ok)')).toBeLessThan(
      section.indexOf('notifyStrategyInputsChanged('),
    );
    expect(section).not.toContain('menuPlan');
    expect(section).not.toContain('MenuPlan');
  });

  it('builds effectiveness from backend payload only', () => {
    expect(viewModel).toContain('buildEffectivenessViewModel');
    expect(viewModel).not.toContain('evaluate');
    expect(viewModel).not.toContain('replacement_count');
  });
});
