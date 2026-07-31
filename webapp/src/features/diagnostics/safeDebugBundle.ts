/**
 * Sprint 9.5 — build a privacy-safe diagnostics clipboard payload.
 * Never include tokens, initData, user IDs, meal names, or profile values.
 */

export interface SafeDebugBundleInput {
  appVersion: string;
  frontendMode: 'development' | 'production';
  apiBaseUrl: string | null;
  healthStatus: string | null;
  readyStatus: string | null;
  authMode: string | null;
  menuGeneration: string | null;
  telegramSdkAvailable: boolean;
  telegramEnvironment: boolean;
  initDataPresent: boolean;
  timezone: string;
  localeDate: string;
  networkOnline: boolean;
  route: string;
  lastErrorCode: string | null;
  lastRequestId: string | null;
  consistencyStatus: string | null;
  consistencyIssues: string[];
  lifecycleCounts: Record<string, number> | null;
  devTools: boolean;
}

const FORBIDDEN =
  /\b(?:user_id|initData|token|Authorization|ANTHROPIC|secret|password)\b/i;

export function buildSafeDebugBundle(input: SafeDebugBundleInput): string {
  const payload = {
    app_version: input.appVersion,
    frontend_mode: input.frontendMode,
    api_base_url: input.apiBaseUrl,
    health: input.healthStatus,
    ready: input.readyStatus,
    auth_mode: input.authMode,
    menu_generation: input.menuGeneration,
    telegram_sdk: input.telegramSdkAvailable,
    telegram_environment: input.telegramEnvironment,
    init_data_present: input.initDataPresent,
    timezone: input.timezone,
    locale_date: input.localeDate,
    network_online: input.networkOnline,
    route: input.route,
    last_error_code: input.lastErrorCode,
    correlation_id: input.lastRequestId,
    consistency: input.consistencyStatus,
    consistency_issues: input.consistencyIssues,
    lifecycle_counts: input.lifecycleCounts,
    dev_tools: input.devTools,
  };

  const text = JSON.stringify(payload, null, 2);
  if (FORBIDDEN.test(text)) {
    return JSON.stringify(
      {
        error: 'Diagnostics bundle blocked: sensitive field detected',
      },
      null,
      2,
    );
  }
  return text;
}
