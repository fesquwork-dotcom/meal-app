import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const source = readFileSync(resolve(__dirname, './InsightCard.tsx'), 'utf-8');

describe('InsightCard', () => {
  it('renders title, summary, confidence, and evidence label', () => {
    expect(source).toContain('insight.title');
    expect(source).toContain('insight.summary');
    expect(source).toContain('insight.confidenceLabel');
    expect(source).toContain('insight.evidenceLabel');
  });

  it('has screen-reader article semantics', () => {
    expect(source).toContain('role="article"');
    expect(source).toContain('aria-labelledby');
    expect(source).toContain('aria-describedby');
    expect(source).toContain('useId');
  });

  it('uses existing Telegram theme tokens', () => {
    expect(source).toContain('text-app-hint');
    expect(source).not.toContain('#');
    expect(source).not.toContain('rgb(');
  });
});

