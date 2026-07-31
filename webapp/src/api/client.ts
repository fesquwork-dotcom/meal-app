import axios from 'axios';
import { getRuntimeConfig } from '@/lib/runtimeConfig';
import { buildTelegramAuthorizationHeader } from '@/lib/telegram';

const runtimeConfig = getRuntimeConfig();

export const api = axios.create({
  baseURL: runtimeConfig.apiBaseUrl ?? undefined,
  timeout: 180000,
});

api.interceptors.request.use((requestConfig) => {
  if (!runtimeConfig.apiBaseUrl) {
    return Promise.reject(new Error('API base URL is not configured'));
  }

  const authorization = buildTelegramAuthorizationHeader();

  if (authorization) {
    requestConfig.headers.Authorization = authorization;
  } else if (requestConfig.headers.Authorization) {
    delete requestConfig.headers.Authorization;
  }

  return requestConfig;
});
