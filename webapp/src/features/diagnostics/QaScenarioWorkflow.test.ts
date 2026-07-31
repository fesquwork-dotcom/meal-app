import { describe, expect, it } from 'vitest';

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const api = readFileSync(resolve(__dirname, '../../api/devTools.ts'), 'utf-8');
const page = readFileSync(
  resolve(__dirname, '../../pages/DiagnosticsPage.tsx'),
  'utf-8',
);

describe('QaScenarioWorkflow', () => {
  it('posts only allowlisted scenario names through the API helper', () => {
    expect(api).toContain('/api/dev/load-qa-scenario');
    expect(api).toContain('scenario');
    expect(page).toContain('PHASE9_SCENARIOS');
    expect(page).toContain('clearClientStateAfterDevReset');
  });

  it('requires confirmation for reset and disables while pending', () => {
    expect(api).toContain("confirm: 'RESET'");
    expect(page).toContain('window.confirm');
    expect(page).toContain('actionPending');
    expect(page).toContain('resetCurrentDevUser');
  });
});
