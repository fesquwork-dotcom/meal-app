# Release Checklist

Use this checklist before a test or production deployment.

## Secrets and auth

- [ ] `TELEGRAM_BOT_TOKEN` configured on backend
- [ ] `BOT_TOKEN` configured for bot process
- [ ] `ANTHROPIC_API_KEY` configured
- [ ] `ALLOW_DEV_AUTH=false`
- [ ] No secrets committed to git
- [ ] No secrets in application logs

## CORS and URLs

- [ ] `ALLOWED_ORIGINS` contains exact production frontend URL
- [ ] No wildcard `*` origin
- [ ] Frontend served over HTTPS
- [ ] Backend served over HTTPS
- [ ] `VITE_API_BASE_URL` points to backend HTTPS URL
- [ ] No localhost URLs in production frontend bundle

## Telegram Mini App

- [ ] Mini App URL configured in BotFather
- [ ] `MINI_APP_URL` set for bot
- [ ] `/start` shows **Открыть приложение** button
- [ ] Button opens Mini App inside Telegram

## Backend health

- [ ] `GET /api/health` returns `status: ok`
- [ ] `GET /api/ready` returns `status: ready` with HTTP 200
- [ ] `auth_mode` is `telegram` in production
- [ ] `telegram_auth_configured` is `true`

## Functional smoke tests

- [ ] `Authorization: tma <initData>` header arrives on protected requests
- [ ] `POST /api/get-profile` returns current Telegram user
- [ ] `POST /api/generate-menu` succeeds
- [ ] Reload restores saved menu plan
- [ ] Basket checked state persists across reload
- [ ] New generation clears basket checked state

## Infrastructure

- [ ] Hosting/reverse-proxy request timeout >= 180–240 seconds on API path
- [ ] SQLite `DATABASE_PATH` writable (persistent volume in Docker, e.g. `/data`)
- [ ] `python scripts/smoke_test.py` passes
- [ ] `python -m pytest` passes
- [ ] `npm run test && npm run build && npm run lint` pass

## Diagnostics safety

- [ ] `/diagnostics` disabled in production unless explicitly enabled
- [ ] Diagnostics does not expose initData, Authorization, tokens, or API keys
