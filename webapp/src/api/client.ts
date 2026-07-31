import axios from 'axios';
import { getRuntimeConfig } from '@/lib/runtimeConfig';
import { buildTelegramAuthorizationHeader } from '@/lib/telegram';

const runtimeConfig = getRuntimeConfig();

export const api = axios.create({
  baseURL: runtimeConfig.apiBaseUrl ?? undefined,
  // Must stay <= reverse-proxy proxy_read_timeout (300s in deploy/nginx/default.conf)
  timeout: 300000,
});

api.interceptors.request.use((requestConfig) => {
  if (runtimeConfig.apiBaseUrl === null) {
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
