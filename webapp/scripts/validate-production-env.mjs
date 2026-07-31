#!/usr/bin/env node
/**
 * Validates production Docker build environment variables.
 * Allows absolute HTTPS API URL or same-origin (edge reverse proxy).
 * Fails when URL uses localhost.
 */

const apiUrl = (process.env.VITE_API_BASE_URL ?? '').trim();
const LOCALHOST_PATTERN = /localhost|127\.0\.0\.1/i;

function fail(message) {
  console.error(`Production build validation failed: ${message}`);
  process.exit(1);
}

if (!apiUrl || apiUrl === 'same-origin') {
  console.log('Production build env validation passed (same-origin /api via reverse proxy)');
  process.exit(0);
}

if (LOCALHOST_PATTERN.test(apiUrl)) {
  fail('VITE_API_BASE_URL must not use localhost in production Docker build');
}

try {
  new URL(apiUrl.endsWith('/') ? apiUrl.slice(0, -1) : apiUrl);
} catch {
  fail('VITE_API_BASE_URL must be a valid URL or "same-origin"');
}

console.log('Production build env validation passed');
