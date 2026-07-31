import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const source = readFileSync(
  resolve(__dirname, './LearnedPreferenceSection.tsx'),
  'utf-8',
);

describe('LearnedPreferenceSection', () => {
  it('renders an accept and a revoke control for candidates', () => {
    expect(source).toContain('Использовать');
    expect(source).toContain('Не использовать');
    expect(source).toContain('acceptPreference');
    expect(source).toContain('revokePreference');
  });

  it('surfaces actual planning effect separately from active lifecycle', () => {
    expect(source).toContain('card.planningEffectLabel');
    expect(source).toContain("card.status === 'active'");
    expect(source).toContain('Отозвать');
  });

  it('renders effectiveness disclosure and optional review actions', () => {
    expect(source).toContain('Как работает это предпочтение');
    expect(source).toContain('Почему мы так считаем');
    expect(source).toContain('Оставить включённым');
    expect(source).toContain('EffectivenessBlock');
    expect(source).toContain('keepLearnedPreferenceReview');
  });

  it('invalidates only future preview and compare after successful writes', () => {
    expect(source).toContain('notifyStrategyInputsChanged(');
    expect(source).toContain("'learned_preference_accepted'");
    expect(source).toContain("'learned_preference_revoked'");
    expect(source).toContain('notifyCoordinator: true');
    expect(source).toContain('runKeepReview');
  });

  it('handles loading, load error, and action error states', () => {
    expect(source).toContain('aria-busy="true"');
    expect(source).toContain('role="alert"');
    expect(source).toContain('Повторить');
  });

  it('uses accessible article semantics and a semantic list', () => {
    expect(source).toContain('role="article"');
    expect(source).toContain('aria-labelledby');
    expect(source).toContain('aria-describedby');
    expect(source).toContain('useId');
    expect(source).toContain('<ul');
  });

  it('uses Telegram theme tokens and no literal colors', () => {
    expect(source).toContain('text-app-hint');
    expect(source).not.toContain('#');
    expect(source).not.toContain('rgb(');
  });

  it('disables actions while an action is pending', () => {
    expect(source).toContain('disabled={isPending}');
    expect(source).toContain('pendingId');
  });
});
