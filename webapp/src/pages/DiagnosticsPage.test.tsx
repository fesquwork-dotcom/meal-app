import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const source = readFileSync(
  resolve(__dirname, '../../pages/DiagnosticsPage.tsx'),
  'utf-8',
);

describe('DiagnosticsPage contract', () => {
  it('shows development mode indicator and QA controls behind dev_tools', () => {
    expect(source).toContain('Режим разработки');
    expect(source).toContain('Сбросить тестовую историю');
    expect(source).toContain('Полностью сбросить тестового пользователя');
    expect(source).toContain('Скопировать диагностическую информацию');
    expect(source).toContain('showDevControls');
    expect(source).toContain('window.confirm');
    expect(source).toContain('disabled={actionPending}');
  });

  it('does not embed secrets or raw initData values', () => {
    expect(source).not.toContain('ANTHROPIC');
    expect(source).not.toContain('getTelegramInitData() ? getTelegramInitData()');
    expect(source).toContain('initData present');
  });

  it('loads Phase 9 scenarios via allowlisted names', () => {
    expect(source).toContain('learned_preference_ineffective');
    expect(source).toContain('review_dismissed');
    expect(source).toContain('loadQaScenario');
  });
});
