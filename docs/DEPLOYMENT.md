# Deployment Guide — MealApp (Ubuntu 24.04 VPS + Docker Compose)

Production domain: **mealapp.ru** / **www.mealapp.ru**
App user on VPS: **mealapp**
App directory: **/opt/meal-app**
SQLite data: **/opt/meal-app-data**

Backend port **8000 is not published** on the host. Edge proxy listens on **80**
(ACME + redirect) and **443** (TLS).

## Architecture

```
Internet
   │
   ├─ :80  mealapp-proxy
   │     ├── /.well-known/acme-challenge/ → /opt/meal-app-certbot
   │     └── other paths → 301 HTTPS
   │
   └─ :443 mealapp-proxy (TLS)
         ├── /api/ → mealapp-backend:8000
         └── /     → mealapp-webapp:80
                         │
                         ▼
                   /opt/meal-app-data → /data/app.db  (SQLite)
```

| Service   | Public ports | Notes |
|-----------|--------------|-------|
| `proxy`   | `80`, `443`  | Edge reverse proxy; TLS termination        |
| `webapp`  | none         | Internal only                              |
| `backend` | none         | Internal only; SQLite on bind mount        |

Telegram bot (`bot/`) is a **separate host process** (not in Compose yet).

---

## 0. One-time VPS prep (as root / sudo)

```bash
# Create app user (if not already present)
sudo adduser --system --group --home /opt/meal-app mealapp
sudo usermod -aG docker mealapp

sudo mkdir -p /opt/meal-app /opt/meal-app-data
sudo chown -R mealapp:mealapp /opt/meal-app /opt/meal-app-data
```

Switch to the app user for all deploy commands:

```bash
sudo -u mealapp -H bash
cd /opt/meal-app
```

---

## 1. Clone repository

```bash
sudo -u mealapp -H bash
cd /opt/meal-app
git clone https://github.com/fesquwork-dotcom/meal-app.git .
# If the directory is not empty, clone into a temp dir and rsync, or:
# git init && git remote add origin … && git fetch && git checkout main
```

Default branch on GitHub is **main**.

---

## 2. Create production `.env`

```bash
cd /opt/meal-app
cp .env.example .env
chmod 600 .env
nano .env
```

### Required variables (fill real values on the VPS only)

| Variable | Notes |
|----------|--------|
| `TELEGRAM_BOT_TOKEN` | BotFather token (same as bot process) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `CLAUDE_MODEL` | Supported Anthropic model id (default in code: `claude-sonnet-4-6`) |
| `STRATEGY_PREVIEW_SECRET` | `openssl rand -hex 32` |
| `ENVIRONMENT` | must be `production` |
| `ALLOW_DEV_AUTH` | must be `false` |
| `DATABASE_PATH` | `/data/app.db` |
| `ALLOWED_ORIGINS` | `https://mealapp.ru,https://www.mealapp.ru` |
| `MEAL_APP_DATA_PATH` | `/opt/meal-app-data` |
| `VITE_API_BASE_URL` | `same-origin` |
| `ANTHROPIC_TRUST_ENV` | `false` |

### Do **not** set in production

- `ALLOW_DEV_AUTH=true`
- `DEV_TELEGRAM_USER_ID`
- `VITE_ENABLE_DIAGNOSTICS=true`
- any `localhost` / `127.0.0.1` in `ALLOWED_ORIGINS` (startup fails when `ENVIRONMENT=production`)

Until TLS is live, temporary HTTP closed-beta CORS:

```env
ALLOWED_ORIGINS=http://mealapp.ru,http://www.mealapp.ru
```

Telegram Mini Apps require **HTTPS** for real users — enable Certbot before inviting users.

### `ANTHROPIC_TRUST_ENV`

| Value | Behavior |
|-------|----------|
| `false` | httpx does **not** use host `HTTP_PROXY` / `HTTPS_PROXY` |
| `true` | honors proxy env vars (VPN / corporate proxy only) |

---

## 3. Validate Compose config

```bash
cd /opt/meal-app
docker compose config
```

Confirm: `proxy` has `80:80`; backend has **no** host `ports` for 8000; volume is `/opt/meal-app-data:/data`.

---

## 4. Build and start

```bash
cd /opt/meal-app
docker compose build
docker compose up -d
```

Backend packaging smoke (required after backend Dockerfile / package changes):

```bash
docker compose build backend
docker compose run --rm --no-deps --entrypoint python backend -c \
  "import generation_jobs; import generation_jobs.exceptions; print('ok')"
```

The backend image uses `COPY . .` with exclusions in `backend/.dockerignore`
(tests, qa, `.env`, `.venv`, `*.db`, caches). Do not reintroduce a fragile
per-package `COPY` whitelist — new runtime packages would be omitted again.

---

## 5. Status and logs

```bash
docker compose ps
docker compose logs -f --tail=200
docker compose logs -f backend
docker compose logs -f proxy
```

Logs must not contain API keys or bot tokens. Rotate immediately if they do.

---

## 6. Health checks

```bash
curl -sS http://127.0.0.1/api/health
curl -sS http://127.0.0.1/api/ready
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1/
```

Expect:

- `/api/health` → `status: ok`, `auth_mode: telegram`, `dev_tools: false`
- `/api/ready` → `status: ready` (or `degraded` if Claude unreachable)
- `/` → HTTP 200

Confirm backend is not on the host:

```bash
ss -lntp | grep 8000 || echo "OK: 8000 not listening on host"
curl -sS --connect-timeout 2 http://127.0.0.1:8000/api/health && echo "BAD: exposed" || echo "OK: not reachable"
```

---

## 7. BotFather + Telegram bot

1. BotFather → Menu Button / Web App → `https://mealapp.ru` (after TLS)
2. Separate process as `mealapp`:

```bash
sudo -u mealapp -H bash
cd /opt/meal-app/bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
# BOT_TOKEN=…  MINI_APP_URL=https://mealapp.ru  BOT_ENVIRONMENT=production
python main.py
```

Prefer a systemd unit later.

---

## 8. Update application (`git pull`)

```bash
sudo -u mealapp -H bash
cd /opt/meal-app
git fetch origin
git checkout main
git pull --ff-only
docker compose build
docker compose up -d
docker compose ps
curl -sS http://127.0.0.1/api/health
```

SQLite under `/opt/meal-app-data` survives rebuilds.

---

## 9. Rebuild / restart only

```bash
cd /opt/meal-app
docker compose build
docker compose up -d
# or restart without rebuild:
docker compose restart
```

---

## 10. Rollback

```bash
cd /opt/meal-app
git rev-parse HEAD
git fetch origin
git checkout <previous-commit-or-tag>
docker compose build
docker compose up -d
```

If schema migrated forward-only, restore SQLite from backup **before** starting rolled-back containers.

---

## 11. Backup SQLite

```bash
cd /opt/meal-app
docker compose stop backend
TS=$(date -u +%Y%m%dT%H%M%SZ)
cp -a /opt/meal-app-data/app.db "/opt/meal-app-data/app.db.bak-$TS"
# Online-safe alternative:
# sqlite3 /opt/meal-app-data/app.db ".backup '/opt/meal-app-data/app.db.bak-$TS'"
docker compose start backend
```

Copy backups off the VPS when possible.

---

## 12. Restore SQLite

```bash
cd /opt/meal-app
docker compose stop backend
cp -a /opt/meal-app-data/app.db "/opt/meal-app-data/app.db.pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
cp -a /opt/meal-app-data/app.db.bak-YYYYMMDDTHHMMSSZ /opt/meal-app-data/app.db
# Container appuser is typically UID 1000:
sudo chown 1000:1000 /opt/meal-app-data/app.db
docker compose start backend
curl -sS http://127.0.0.1/api/ready
```

---

## 13. Stop application

```bash
cd /opt/meal-app
docker compose down
# Bind-mounted /opt/meal-app-data is kept
```

---

## HTTPS enablement (certificate already issued)

Prerequisites:

- DNS for `mealapp.ru` / `www.mealapp.ru` points at the VPS
- ACME webroot mount already works (`MEAL_APP_CERTBOT_WEBROOT` → `/var/www/certbot`)
- Host certificates exist:
  - `/etc/letsencrypt/live/mealapp.ru/fullchain.pem`
  - `/etc/letsencrypt/live/mealapp.ru/privkey.pem`

### 1. Pull HTTPS config and recreate proxy

```bash
sudo -u mealapp -H bash
cd /opt/meal-app
git fetch origin
git checkout main
git pull --ff-only

# CORS must be HTTPS once TLS is live
# In .env:
# ALLOWED_ORIGINS=https://mealapp.ru,https://www.mealapp.ru

docker compose config
docker compose up -d --force-recreate --no-deps proxy
docker compose ps proxy
```

Confirm mounts and ports:

```bash
docker inspect mealapp-proxy --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Mode}}){{"\n"}}{{end}}'
# Expect among others:
#   /opt/meal-app-certbot -> /var/www/certbot
#   /etc/letsencrypt -> /etc/letsencrypt

docker compose ps
ss -lntp | grep -E ':80|:443' || true
```

### 2. Verify HTTPS and HTTP redirect

```bash
# Health over HTTPS
curl -sS https://mealapp.ru/api/health
curl -sS https://www.mealapp.ru/api/health

# SPA
curl -sS -o /dev/null -w "%{http_code}\n" https://mealapp.ru/

# HTTP must redirect to HTTPS (except ACME)
curl -sSI http://mealapp.ru/ | head -n 5
# Expect: HTTP/1.1 301 … Location: https://mealapp.ru/

# ACME still on plain HTTP (no redirect)
echo ok-challenge > /opt/meal-app-certbot/.well-known/acme-challenge/ping-test
curl -sS http://mealapp.ru/.well-known/acme-challenge/ping-test
rm -f /opt/meal-app-certbot/.well-known/acme-challenge/ping-test

# Backend still not on host
curl -sS --connect-timeout 2 http://127.0.0.1:8000/api/health && echo BAD || echo OK
```

### 3. BotFather

Set Mini App / Menu Button URL to `https://mealapp.ru`.

### 4. Certificate renewal (Certbot on the VPS host)

Certificates are mounted from the host into `mealapp-proxy`. After renew, **reload nginx** so it re-reads PEM files (symlinks under `live/` update in place).

Dry-run:

```bash
sudo certbot renew --dry-run
```

After a real renew (or to apply immediately):

```bash
docker exec mealapp-proxy nginx -t
docker exec mealapp-proxy nginx -s reload
```

Optional deploy hook (`/etc/letsencrypt/renewal-hooks/deploy/reload-mealapp-proxy.sh`):

```bash
#!/bin/sh
docker exec mealapp-proxy nginx -s reload
```

```bash
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-mealapp-proxy.sh
```

Do **not** delete `/opt/meal-app-certbot` — renewals still use HTTP-01 webroot.

### Claude model (`CLAUDE_MODEL`)

Production generation uses `CLAUDE_MODEL` from `.env` (Compose `env_file`).  
Code default (if unset): `claude-sonnet-4-6`.

Retired IDs such as `claude-3-5-sonnet-20241022` and `claude-sonnet-4-20250514`
return Anthropic `404 not_found_error`. After changing the model:

```bash
# In /opt/meal-app/.env
CLAUDE_MODEL=claude-sonnet-4-6

cd /opt/meal-app
docker compose up -d --force-recreate --no-deps backend
# No image rebuild required when only .env changes (runtime config).
```

### Async generation jobs (`GENERATION_MAX_CONCURRENT_JOBS`)

Menu generation runs as in-process async jobs (no Celery/Redis).  
Production UI uses `POST /api/generation-jobs` + polling; the legacy
`POST /api/generate-menu` remains for compatibility/tests only.

`GENERATION_MAX_CONCURRENT_JOBS` caps how many Claude runs execute at once
(default `1`). Keep it low on a single-SQLite VPS.

**Restart behavior (v1):** jobs with status `running` are marked failed with
`GENERATION_INTERRUPTED` on startup (no automatic re-run — avoids duplicate
Anthropic cost / menu persistence). Jobs still `queued` are resumed by the
worker. Schema is created automatically via `init_db()` (`generation_jobs`
table); no separate migration command.

Duplicate prevention: if the same Telegram user already has a `queued` or
`running` job, `POST /api/generation-jobs` returns that job’s `job_id`
(202) instead of starting another Claude run.

### Budget optimizer (manual acceptance)

Profile: 5 days, 1 person, breakfast+lunch+dinner, budget **5000 ₽**.

Expect:
- valid menu, leftover relationships intact;
- authoritative `shopping_cost` ≤ 5000;
- preferred utilization 4500–5000 (90–100%);
- at most **2** soft optimizer corrections after the first valid menu;
- if target is unreachable safely, baseline valid menu is returned and
  `budget_optimizer_completed` is logged with a reason.

Authoritative metric: BasketEngine `shopping_cost` (not Claude `model_total`).

---

## Timeouts

| Layer | Value |
|-------|-------|
| Frontend axios (legacy sync generate) | 300000 ms |
| Frontend axios (generation-jobs create/poll) | 15000 ms |
| Edge nginx `proxy_*_timeout` | 300s (legacy sync; async jobs do not need it) |

Production generation must not depend on a single long HTTP request.

---

## Security checklist

- [ ] `.env` mode `600`, owned by `mealapp`, never in git
- [ ] `ALLOW_DEV_AUTH=false`, `ENVIRONMENT=production`
- [ ] `/api/health` shows `dev_tools: false`
- [ ] Backend `:8000` not on host
- [ ] No localhost in production frontend bundle / CORS
- [ ] HTTPS live (`https://mealapp.ru/api/health`)
- [ ] HTTP redirects to HTTPS; ACME still on port 80
- [ ] Certbot renew dry-run + `nginx -s reload` documented

---

## Troubleshooting

**401 Telegram auth** — open from bot button; token must match the bot that opened the Mini App.

**CORS** — `ALLOWED_ORIGINS` must match exact scheme + host.

**Generation aborts early** — confirm nginx timeouts are 300s; no shorter host proxy in front.

**SQLite permission denied** — `sudo chown -R 1000:1000 /opt/meal-app-data`.

---

## Known limitations

- CSP not configured (Telegram WebApp script).
- Bot not in Compose.
