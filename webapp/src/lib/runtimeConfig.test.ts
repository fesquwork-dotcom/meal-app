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

  if (!trimmed || trimmed === 'same-origin') {
    if (useDevelopmentFallback && !trimmed) {
      return 'http://localhost:8000';
    }
    return '';
  }

  try {
    const url = new URL(trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed);
    return url.origin;
  } catch {
    return null;
  }
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

  it('accepts same-origin mode in production', () => {
    const apiBaseUrl = resolveApiBaseUrlFromEnv('same-origin', false);

    expect(apiBaseUrl).toBe('');
    expect(validateApiBaseUrl(apiBaseUrl, true)).toBeNull();
  });

  it('rejects invalid URL format', () => {
    const apiBaseUrl = resolveApiBaseUrlFromEnv('not-a-url', false);

    expect(apiBaseUrl).toBeNull();
    expect(validateApiBaseUrl(apiBaseUrl, true)).not.toBeNull();
  });
});

describe('validateProductionBuildApiUrl', () => {
  it('accepts empty and same-origin production API URL', () => {
    expect(validateProductionBuildApiUrl('')).toBeNull();
    expect(validateProductionBuildApiUrl(undefined)).toBeNull();
    expect(validateProductionBuildApiUrl('same-origin')).toBeNull();
  });

  it('rejects localhost production API URL', () => {
    expect(validateProductionBuildApiUrl('http://localhost:8000')).toContain('localhost');
  });

  it('accepts valid HTTPS production API URL', () => {
    expect(validateProductionBuildApiUrl('https://api.example.com/')).toBeNull();
  });
});
