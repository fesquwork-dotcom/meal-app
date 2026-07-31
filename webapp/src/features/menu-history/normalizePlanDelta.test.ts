import { describe, expect, it } from 'vitest';

import { normalizePlanDelta } from '@/features/menu-history/normalizePlanDelta';

const availableMetric = {
  id: 'total_cost',
  status: 'available',
  unit: 'rub',
  original: 2700,
  current: 2450,
  delta: -250,
  direction: 'decreased',
};

describe('normalizePlanDelta', () => {
  it('keeps valid available metrics', () => {
    const delta = normalizePlanDelta({ version: 1, metrics: [availableMetric] });
    expect(delta?.metrics).toHaveLength(1);
    expect(delta?.metrics[0].delta).toBe(-250);
    expect(delta?.metrics[0].direction).toBe('decreased');
  });

  it('normalizes unavailable metrics to an all-null shape', () => {
    const delta = normalizePlanDelta({
      version: 1,
      metrics: [
        {
          id: 'calories',
          status: 'unavailable',
          unit: 'kcal',
          original: 100,
          delta: 5,
          direction: 'increased',
        },
      ],
    });
    const metric = delta?.metrics[0];
    expect(metric?.status).toBe('unavailable');
    expect(metric?.original).toBeNull();
    expect(metric?.delta).toBeNull();
    expect(metric?.direction).toBeNull();
  });

  it('drops metrics with unknown ids, units, or malformed numbers', () => {
    const delta = normalizePlanDelta({
      version: 1,
      metrics: [
        { ...availableMetric, id: 'secret_metric' },
        { ...availableMetric, unit: 'usd' },
        { ...availableMetric, delta: 'много' },
        { ...availableMetric, direction: 'sideways' },
        availableMetric,
      ],
    });
    expect(delta?.metrics).toHaveLength(1);
  });

  it('returns null for malformed payloads', () => {
    expect(normalizePlanDelta(null)).toBeNull();
    expect(normalizePlanDelta('x')).toBeNull();
  });

  it('caps the metric count', () => {
    const delta = normalizePlanDelta({
      version: 1,
      metrics: Array.from({ length: 30 }, () => availableMetric),
    });
    expect(delta?.metrics.length).toBeLessThanOrEqual(12);
  });
});
