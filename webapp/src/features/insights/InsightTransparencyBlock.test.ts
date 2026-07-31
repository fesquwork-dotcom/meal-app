import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const source = readFileSync(resolve(__dirname, './InsightTransparencyBlock.tsx'), 'utf-8');

describe('InsightTransparencyBlock', () => {
  it('implements the disclosure pattern', () => {
    expect(source).toContain('aria-expanded={isOpen}');
    expect(source).toContain('aria-controls={panelId}');
    expect(source).toContain('useId');
    expect(source).toContain('type="button"');
  });

  it('renders backend-provided texts without composing its own', () => {
    expect(source).toContain('transparency.toggleLabel');
    expect(source).toContain('line.text');
    expect(source).not.toContain('strategy_id');
    expect(source).not.toContain('user_id');
  });

  it('logs open and close events without PII', () => {
    expect(source).toContain('insight_transparency_opened');
    expect(source).toContain('insight_transparency_closed');
    expect(source).toContain('import.meta.env.DEV');
    expect(source).not.toContain('generated_at');
  });

  it('uses existing Telegram theme tokens and hides decorations from readers', () => {
    expect(source).toContain('text-app-link');
    expect(source).toContain('text-app-hint');
    expect(source).toContain('aria-hidden="true"');
    expect(source).not.toContain('rgb(');
  });
});
