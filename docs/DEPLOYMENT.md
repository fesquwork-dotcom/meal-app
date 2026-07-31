# Deployment Guide

This guide prepares Meal Planner for a **test deployment** with Telegram Mini App authentication.

## Architecture

- **Frontend**: static SPA served by nginx (`webapp/Dockerfile`)
- **Backend**: FastAPI + SQLite (`backend/Dockerfile`)
- **Bot**: aiogram bot with Web App button (`bot/main.py`)

Frontend nginx serves **static files only**. API requests go directly from the browser to `VITE_API_BASE_URL`.

## 1. Prepare Telegram bot token

1. Open [@BotFather](https://t.me/BotFather)
2. Create or select your bot
3. Save `BOT_TOKEN` for the bot process
4. Save the same bot token as `TELEGRAM_BOT_TOKEN` for backend initData verification

Do not commit tokens to git.

## 2. Prepare Claude API key

1. Create an Anthropic API key
2. Set `ANTHROPIC_API_KEY` in backend environment

## 3. Configure backend environment

Copy `backend/.env.example` to `backend/.env` and set:

```env
TELEGRAM_BOT_TOKEN=<from BotFather>
ANTHROPIC_API_KEY=<your key>
CLAUDE_MODEL=claude-3-5-sonnet-20241022
ALLOW_DEV_AUTH=false
ALLOWED_ORIGINS=https://your-frontend.example.com
DATABASE_PATH=/data/app.db
STRATEGY_PREVIEW_SECRET=<random 32+ byte secret>
PREVIEW_TOKEN_TTL_SECONDS=900
ENVIRONMENT=production
```

Startup validation fails fast when:

- `ALLOW_DEV_AUTH=false` and `TELEGRAM_BOT_TOKEN` is empty
- `ALLOWED_ORIGINS` is empty or contains `*`
- `ANTHROPIC_API_KEY` is missing
- `STRATEGY_PREVIEW_SECRET` is missing (required for signed preview tokens)
- database parent directory is not writable

### Preview token secret rotation

`STRATEGY_PREVIEW_SECRET` signs short-lived strategy preview tokens returned by `POST /api/strategy/preview`. Rotating this secret invalidates all outstanding preview tokens immediately. Users must request a new preview before generating a menu. Do not expose this secret to the frontend.

### Profile revision migration (Sprint 5.17)

Deploy backend before frontend. Existing profiles receive `revision = 1` via additive SQLite migration. New clients require `GET/PUT /api/profile` with `expected_revision`.

### Server-owned generation context (Sprint 5.18)

Deploy backend and frontend together when possible. Token version is **3** (`plan_start_date` bound in token). Existing preview tokens (v1/v2) are rejected with `STRATEGY_PREVIEW_VERSION_MISMATCH`.

| Removed | Replacement |
| ------- | ----------- |
| Profile fields in preview/generate body | `GET/PUT /api/profile` |
| `preview_fingerprint` | `preview_token` |
| generation without preview | always `428 STRATEGY_PREVIEW_REQUIRED` |
| `POST /api/get-profile` | `GET /api/profile` |
| `ALLOW_LEGACY_GENERATION_WITHOUT_PREVIEW` | removed |

Preview body: `{}` or `{ "plan_start_date": "YYYY-MM-DD" }`. Generate body: `{ "preview_token": "..." }` only.

### Server-owned conflict resolution (Sprint 5.19)

Deploy backend before frontend. Resolve body: `{ "preview_token", "conflict_id", "action" }` only. Profile fields in resolve request return HTTP 422.

## 4. Deploy backend

```bash
cd backend
docker build -t meal-planner-api .
docker run --env-file .env -p 8000:8000 -v meal-data:/data meal-planner-api
```

Or run locally:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Set `PORT` when deploying to platforms that inject it (Docker image uses `docker_entrypoint.py`).

## 5. Verify backend endpoints

```bash
python scripts/smoke_test.py --base-url https://api.example.com
```

Manual checks:

- `GET /api/health` → `status: ok`, no secrets
- `GET /api/ready` → `status: ready`, HTTP 200

## 6. Configure frontend

Copy `webapp/.env.example` to `webapp/.env.production`:

```env
VITE_API_BASE_URL=https://api.example.com
VITE_ENABLE_DIAGNOSTICS=false
```

Production build must **not** use localhost API URL.

## 7. Deploy frontend

```bash
cd webapp
docker build \
  --build-arg VITE_API_BASE_URL=https://api.example.com \
  --build-arg VITE_ENABLE_DIAGNOSTICS=false \
  -t meal-planner-web .
docker run -p 8080:80 meal-planner-web
```

Docker build fails if `VITE_API_BASE_URL` is empty or uses localhost.

## 8. Configure Mini App URL in BotFather

1. BotFather → your bot → Bot Settings → Menu Button / Web App
2. Set HTTPS frontend URL, e.g. `https://your-frontend.example.com`

## 9. Configure bot environment

Copy `bot/.env.example` to `bot/.env`:

```env
BOT_TOKEN=<same bot token>
MINI_APP_URL=https://your-frontend.example.com
BOT_ENVIRONMENT=production
```

Run bot:

```bash
cd bot
pip install -r requirements.txt
python main.py
```

## 10. Test via Telegram

1. Send `/start` to your bot
2. Tap **Открыть приложение**
3. Confirm Mini App loads inside Telegram

## 11. Verify Telegram Authorization

- Protected API calls send `Authorization: tma <initData>`
- `GET /api/profile` returns current Telegram user
- `POST /api/generate-menu` works for the same user
- Reload restores menu plan and basket checked state from localStorage

## 12. Disable development auth

Before real users:

```env
ALLOW_DEV_AUTH=false
```

Restart backend and confirm `/api/health` returns `auth_mode: "telegram"`.

---

## Timeout requirements

Menu generation may take up to **180 seconds** on the client side.

| Layer | Responsibility |
|-------|----------------|
| Frontend axios | `timeout: 180000` ms — client aborts after 180s |
| Backend application | Does **not** cancel in-flight generation by default |
| Hosting platform / reverse proxy | Must allow the request for at least **180–240 seconds** |

**Important:** Uvicorn `--timeout-keep-alive` controls only HTTP keep-alive between requests on a persistent connection. It does **not** set the maximum duration of `POST /api/generate-menu`. This project runs Uvicorn without a custom keep-alive override.

If you add Gunicorn in front of Uvicorn, set worker timeout to at least **240 seconds** (for example `gunicorn --timeout 240`).

**Warning:** hosting platforms with hard request timeouts below 180 seconds may interrupt menu generation even when the backend is still working.

Frontend nginx in this repo serves static files only and does **not** proxy API requests.

---

## Docker persistence

Backend container default:

```env
DATABASE_PATH=/data/app.db
```

Mount a **persistent volume** at `/data` so SQLite survives container restarts:

```bash
docker run --env-file .env -p 8000:8000 -v meal-data:/data meal-planner-api
```

Override `DATABASE_PATH` if your platform uses a different mount path.

The `appuser` non-root user owns `/data` (created with correct permissions in `backend/Dockerfile`).

Backend listens on `0.0.0.0` and honors `PORT` (default `8000`) via `docker_entrypoint.py`.

---

## Content Security Policy

CSP is **not** configured in `nginx.conf`. The frontend loads `https://telegram.org/js/telegram-web-app.js` and calls the backend API directly. Adding a strict CSP without testing may break the Mini App. Treat missing CSP as a known limitation for the first test deployment.

---

## CORS

Backend allows only explicit origins from `ALLOWED_ORIGINS`.

Required for Mini App:

- production frontend HTTPS origin
- development: `http://localhost:5173`, `http://127.0.0.1:5173`

`Authorization` header is allowed via `allow_headers=["*"]`.

Preflight `OPTIONS` is handled by FastAPI CORS middleware for `/api/profile` and `/api/generate-menu`.

---

## Troubleshooting

### 401 Telegram authentication failed

- Open app from Telegram bot button, not external browser
- Ensure backend `TELEGRAM_BOT_TOKEN` matches the bot that opened the Mini App
- Confirm `ALLOW_DEV_AUTH=false` only after Telegram flow works

### CORS error

- Add exact frontend origin to `ALLOWED_ORIGINS`
- Do not use `*` with credentials

### Blank screen

- Check browser console
- Verify `VITE_API_BASE_URL` in production build
- Open `/diagnostics` in development or with `VITE_ENABLE_DIAGNOSTICS=true`

### API unreachable

- Verify backend URL and HTTPS certificate
- Run `scripts/smoke_test.py`

### initData missing

- App was opened outside Telegram
- Telegram SDK script failed to load

### Claude timeout

- Ensure hosting platform or reverse proxy allows at least **180–240 seconds** for API requests
- Uvicorn keep-alive does not control request duration; check platform/proxy timeout settings

### SQLite permission error

- Ensure `DATABASE_PATH` parent directory is writable
- In Docker, mount a writable volume (e.g. `/data`)

### Wrong frontend origin

- `ALLOWED_ORIGINS` must match exact scheme + host + port

---

## Diagnostics route

`/diagnostics` is available in development or when:

```env
VITE_ENABLE_DIAGNOSTICS=true
```

It shows only safe runtime flags and never exposes initData, tokens, or API keys.
