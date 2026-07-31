import { describe, expect, it } from 'vitest';

import profileApiSource from '@/api/profile.ts?raw';
import memoryApiSource from '@/api/memory.ts?raw';
import behaviorApiSource from '@/api/behavior.ts?raw';
import loaderOptionsSource from '@/api/resourceLoaderOptions.ts?raw';

/**
 * Sprint 5.35 architectural decision: mutations are not cancellable from the
 * client. A POST/PUT may complete on the server after a client abort, leaving
 * the UI believing the operation was cancelled. Without idempotency keys /
 * status reconciliation, mutation functions must not accept AbortSignal.
 */

function extractFunction(source: string, name: string): string {
  const start = source.indexOf(`export async function ${name}(`);
  expect(start, `function ${name} not found`).toBeGreaterThan(-1);
  const nextExport = source.indexOf('export ', start + 1);
  return nextExport === -1 ? source.slice(start) : source.slice(start, nextExport);
}

const MUTATIONS: Array<[string, string]> = [
  [profileApiSource, 'saveProfile'],
  [memoryApiSource, 'confirmMemorySignal'],
  [memoryApiSource, 'dismissMemorySignal'],
  [memoryApiSource, 'promoteMemorySignal'],
  [behaviorApiSource, 'confirmBehaviorInsight'],
  [behaviorApiSource, 'dismissBehaviorInsight'],
  [behaviorApiSource, 'snoozeBehaviorInsight'],
  [behaviorApiSource, 'revokeBehaviorInsight'],
  [behaviorApiSource, 'applyBehaviorRecommendation'],
];

describe('mutation cancellation policy', () => {
  it.each(MUTATIONS.map(([source, name]) => [name, source] as const))(
    '%s does not accept an AbortSignal / ResourceLoaderOptions',
    (name, source) => {
      const fn = extractFunction(source, name);
      expect(fn).not.toContain('ResourceLoaderOptions');
      expect(fn).not.toContain('AbortSignal');
      expect(fn).not.toContain('signal:');
    },
  );

  it('read loaders still accept the signal (GET only)', () => {
    expect(extractFunction(profileApiSource, 'getProfile')).toContain('ResourceLoaderOptions');
    expect(extractFunction(memoryApiSource, 'getMemorySignals')).toContain('ResourceLoaderOptions');
    expect(extractFunction(behaviorApiSource, 'getBehaviorInsights')).toContain(
      'ResourceLoaderOptions',
    );
  });

  it('the decision is documented next to ResourceLoaderOptions', () => {
    expect(loaderOptionsSource).toContain('Mutation cancellation policy');
    expect(loaderOptionsSource).toContain('do NOT accept an AbortSignal');
    expect(loaderOptionsSource).toContain('idempotency');
  });
});
