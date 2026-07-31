import {
  getTelegramInitData,
  isTelegramEnvironment,
  isTelegramWebAppAvailable,
} from '@/lib/telegram';

export interface RuntimeConfigSnapshot {
  apiBaseUrl: string | null;
  isProduction: boolean;
  isDevelopment: boolean;
  configError: string | null;
  telegramSdkAvailable: boolean;
  telegramEnvironment: boolean;
  initDataPresent: boolean;
}

const LOCALHOST_PATTERN = /localhost|127\.0\.0\.1/i;
const SAME_ORIGIN_TOKEN = 'same-origin';

function isSameOriginToken(raw: string | undefined): boolean {
  const trimmed = raw?.trim();
  return !trimmed || trimmed === SAME_ORIGIN_TOKEN;
}

function normalizeApiBaseUrl(raw: string | undefined): string | null {
  const trimmed = raw?.trim();

  if (!trimmed || trimmed === SAME_ORIGIN_TOKEN) {
    return null;
  }

  try {
    const url = new URL(trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed);
    return url.origin;
  } catch {
    return null;
  }
}

/** Resolves same-origin mode to the current page origin (or '' when window is unavailable). */
export function resolveSameOriginApiBaseUrl(): string {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return '';
}

export function validateApiBaseUrl(
  apiBaseUrl: string | null,
  isProduction: boolean,
): string | null {
  if (apiBaseUrl === null) {
    return isProduction
      ? 'Не задан корректный VITE_API_BASE_URL для production-сборки.'
      : null;
  }

  // Empty string = relative same-origin mode (edge proxy /api).
  if (apiBaseUrl === '') {
    return null;
  }

  if (isProduction && LOCALHOST_PATTERN.test(apiBaseUrl)) {
    return 'Production-сборка не может использовать localhost API URL.';
  }

  return null;
}

export function validateProductionBuildApiUrl(raw: string | undefined): string | null {
  const trimmed = raw?.trim();

  if (isSameOriginToken(trimmed)) {
    return null;
  }

  if (LOCALHOST_PATTERN.test(trimmed!)) {
    return 'VITE_API_BASE_URL must not use localhost in production build';
  }

  const normalized = normalizeApiBaseUrl(trimmed);

  if (!normalized) {
    return 'VITE_API_BASE_URL must be a valid URL';
  }

  return null;
}

function resolveApiBaseUrl(): string | null {
  const raw = import.meta.env.VITE_API_BASE_URL;

  if (isSameOriginToken(raw)) {
    // Vite dev server does not proxy /api — keep local backend in development.
    if (import.meta.env.DEV) {
      return 'http://localhost:8000';
    }
    // Production: browser origin behind edge reverse proxy (/api → backend).
    return resolveSameOriginApiBaseUrl();
  }

  return normalizeApiBaseUrl(raw);
}

/** Validates frontend runtime configuration without logging secrets. */
export function getRuntimeConfig(): RuntimeConfigSnapshot {
  const isProduction = import.meta.env.PROD;
  const isDevelopment = import.meta.env.DEV;
  const apiBaseUrl = resolveApiBaseUrl();
  const telegramSdkAvailable = isTelegramWebAppAvailable();
  const telegramEnvironment = isTelegramEnvironment();
  const initDataPresent = Boolean(getTelegramInitData());
  const configError = validateApiBaseUrl(apiBaseUrl, isProduction);

  return {
    apiBaseUrl,
    isProduction,
    isDevelopment,
    configError,
    telegramSdkAvailable,
    telegramEnvironment,
    initDataPresent,
  };
}

export function isDiagnosticsEnabled(): boolean {
  if (import.meta.env.DEV) {
    return true;
  }

  return import.meta.env.VITE_ENABLE_DIAGNOSTICS === 'true';
}
