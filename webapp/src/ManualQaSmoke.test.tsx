import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const app = readFileSync(resolve(__dirname, '../App.tsx'), 'utf-8');
const diagnostics = readFileSync(
  resolve(__dirname, '../pages/DiagnosticsPage.tsx'),
  'utf-8',
);
const learned = readFileSync(
  resolve(
    __dirname,
    '../features/learned-preferences/LearnedPreferenceSection.tsx',
  ),
  'utf-8',
);

describe('ManualQaSmoke', () => {
  it('wires diagnostics route and learned preference review actions', () => {
    expect(app).toContain('/diagnostics');
    expect(app).toContain('DiagnosticsPage');
    expect(diagnostics).toContain('Backend health');
    expect(diagnostics).toContain('Скопировать диагностическую информацию');
    expect(learned).toContain('Оставить включённым');
    expect(learned).toContain('Почему мы так считаем');
    expect(learned).toContain('notifyCoordinator');
  });
});
