import { describe, expect, it } from 'vitest';

import type { GenerateMenuRequest, StrategyPreviewRequest } from '@/types/api';

describe('server-owned API request contracts', () => {
  it('preview request contains only allowed fields', () => {
    const request: StrategyPreviewRequest = { plan_start_date: '2026-07-13' };
    expect(Object.keys(request)).toEqual(['plan_start_date']);
  });

  it('generate request contains only preview token', () => {
    const request: GenerateMenuRequest = { preview_token: 'signed-token' };
    expect(Object.keys(request)).toEqual(['preview_token']);
    expect(request).not.toHaveProperty('allergies');
    expect(request).not.toHaveProperty('budget');
    expect(request).not.toHaveProperty('proteins');
  });
});
