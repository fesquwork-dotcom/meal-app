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

function normalizeApiBaseUrl(raw: string | undefined): string | null {
  const trimmed = raw?.trim();

  if (!trimmed) {
    return null;
  }

  try {
    const url = new URL(trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed);
    return url.origin;
  } catch {
    return null;
  }
}

export function validateApiBaseUrl(
  apiBaseUrl: string | null,
  isProduction: boolean,
): string | null {
  if (!apiBaseUrl) {
    return isProduction
      ? 'Не задан корректный VITE_API_BASE_URL для production-сборки.'
      : null;
  }

  if (isProduction && LOCALHOST_PATTERN.test(apiBaseUrl)) {
    return 'Production-сборка не может использовать localhost API URL.';
  }

  return null;
}

export function validateProductionBuildApiUrl(raw: string | undefined): string | null {
  const trimmed = raw?.trim();

  if (!trimmed) {
    return 'VITE_API_BASE_URL is required for production build';
  }

  if (LOCALHOST_PATTERN.test(trimmed)) {
    return 'VITE_API_BASE_URL must not use localhost in production build';
  }

  const normalized = normalizeApiBaseUrl(trimmed);

  if (!normalized) {
    return 'VITE_API_BASE_URL must be a valid URL';
  }

  return null;
}

function resolveApiBaseUrl(): string | null {
  const configured = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

  if (configured) {
    return configured;
  }

  if (import.meta.env.DEV) {
    return 'http://localhost:8000';
  }

  return null;
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
