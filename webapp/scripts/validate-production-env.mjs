#!/usr/bin/env node
/**
 * Validates production Docker build environment variables.
 * Fails the image build when API URL is missing or uses localhost.
 */

const apiUrl = (process.env.VITE_API_BASE_URL ?? '').trim();
const LOCALHOST_PATTERN = /localhost|127\.0\.0\.1/i;

function fail(message) {
  console.error(`Production build validation failed: ${message}`);
  process.exit(1);
}

if (!apiUrl) {
  fail('VITE_API_BASE_URL is required for production Docker build');
}

if (LOCALHOST_PATTERN.test(apiUrl)) {
  fail('VITE_API_BASE_URL must not use localhost in production Docker build');
}

try {
  new URL(apiUrl.endsWith('/') ? apiUrl.slice(0, -1) : apiUrl);
} catch {
  fail('VITE_API_BASE_URL must be a valid URL');
}

console.log('Production build env validation passed');
