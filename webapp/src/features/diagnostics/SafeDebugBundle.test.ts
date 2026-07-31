import { describe, expect, it } from 'vitest';

import { buildSafeDebugBundle } from '@/features/diagnostics/safeDebugBundle';

describe('SafeDebugBundle', () => {
  it('includes safe fields and omits secrets', () => {
    const text = buildSafeDebugBundle({
      appVersion: '9.5.0',
      frontendMode: 'development',
      apiBaseUrl: 'http://localhost:8000',
      healthStatus: 'ok',
      readyStatus: 'degraded',
      authMode: 'development',
      menuGeneration: 'not_configured',
      telegramSdkAvailable: false,
      telegramEnvironment: false,
      initDataPresent: false,
      timezone: 'Europe/Moscow',
      localeDate: '16.07.2026',
      networkOnline: true,
      route: '/diagnostics',
      lastErrorCode: 'SERVICE_UNAVAILABLE',
      lastRequestId: 'req_abc',
      consistencyStatus: 'ok',
      consistencyIssues: [],
      lifecycleCounts: { strategies: 1 },
      devTools: true,
    });
    expect(text).toContain('"app_version": "9.5.0"');
    expect(text).toContain('"correlation_id": "req_abc"');
    expect(text).not.toContain('initData');
    expect(text).not.toContain('ANTHROPIC');
    expect(text).not.toContain('user_id');
  });
});
