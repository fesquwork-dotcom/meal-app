import { describe, expect, it } from 'vitest';
import {
  validateApiBaseUrl,
  validateProductionBuildApiUrl,
} from '@/lib/runtimeConfig';

function resolveApiBaseUrlFromEnv(
  viteApiBaseUrl: string | undefined,
  useDevelopmentFallback: boolean,
): string | null {
  const trimmed = viteApiBaseUrl?.trim();

  if (trimmed) {
    try {
      const url = new URL(trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed);
      return url.origin;
    } catch {
      return null;
    }
  }

  if (useDevelopmentFallback) {
    return 'http://localhost:8000';
  }

  return null;
}

describe('runtime API URL validation', () => {
  it('allows localhost API URL in development fallback', () => {
    const apiBaseUrl = resolveApiBaseUrlFromEnv('', true);

    expect(apiBaseUrl).toBe('http://localhost:8000');
    expect(validateApiBaseUrl(apiBaseUrl, false)).toBeNull();
  });

  it('rejects localhost API URL in production', () => {
    const apiBaseUrl = resolveApiBaseUrlFromEnv('http://localhost:8000', false);

    expect(validateApiBaseUrl(apiBaseUrl, true)).toContain('localhost');
  });

  it('accepts valid HTTPS API URL in production', () => {
    const apiBaseUrl = resolveApiBaseUrlFromEnv('https://api.example.com/', false);

    expect(apiBaseUrl).toBe('https://api.example.com');
    expect(validateApiBaseUrl(apiBaseUrl, true)).toBeNull();
  });

  it('reports missing API URL in production', () => {
    const apiBaseUrl = resolveApiBaseUrlFromEnv('', false);

    expect(apiBaseUrl).toBeNull();
    expect(validateApiBaseUrl(apiBaseUrl, true)).not.toBeNull();
  });

  it('rejects invalid URL format', () => {
    const apiBaseUrl = resolveApiBaseUrlFromEnv('not-a-url', false);

    expect(apiBaseUrl).toBeNull();
    expect(validateApiBaseUrl(apiBaseUrl, true)).not.toBeNull();
  });
});

describe('validateProductionBuildApiUrl', () => {
  it('rejects empty production API URL', () => {
    expect(validateProductionBuildApiUrl('')).not.toBeNull();
    expect(validateProductionBuildApiUrl(undefined)).not.toBeNull();
  });

  it('rejects localhost production API URL', () => {
    expect(validateProductionBuildApiUrl('http://localhost:8000')).toContain('localhost');
  });

  it('accepts valid HTTPS production API URL', () => {
    expect(validateProductionBuildApiUrl('https://api.example.com/')).toBeNull();
  });
});
