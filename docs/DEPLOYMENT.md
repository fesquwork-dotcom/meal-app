# Deployment Guide — MealApp (Ubuntu 24.04 VPS + Docker Compose)

Production domain: **mealapp.ru** / **www.mealapp.ru**
App user on VPS: **mealapp**
App directory: **/opt/meal-app**
SQLite data: **/opt/meal-app-data**

Backend port **8000 is not published** on the host. Only the edge proxy listens on **80**
(HTTPS / 443 is a separate Certbot step after DNS).

## Architecture

```
Internet
   │
   ▼
:80  mealapp-proxy (nginx)
   ├── /                       → mealapp-webapp:80   (Vite static SPA)
   ├── /api/                   → mealapp-backend:8000 (FastAPI)
   └── /.well-known/acme-challenge/  → host MEAL_APP_CERTBOT_WEBROOT (/opt/meal-app-certbot)
                         │
                         ▼
                   /opt/meal-app-data → /data/app.db  (SQLite)
```

| Service   | Public ports | Notes |
|-----------|--------------|-------|
| `proxy`   | `80`         | Edge reverse proxy; Certbot-ready |
| `webapp`  | none         | Internal only |
| `backend` | none         | Internal only; SQLite on bind mount |

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

## HTTPS preparation (ACME webroot — do this before Certbot)

DNS must already point `mealapp.ru` and `www.mealapp.ru` to the VPS.
TLS server blocks are **not** enabled in-repo yet. First make HTTP-01 challenges work.

### 1. Pull the ACME webroot mount

```bash
sudo -u mealapp -H bash
cd /opt/meal-app
git fetch origin
git checkout main
git pull --ff-only
```

Ensure `.env` contains (or add):

```env
MEAL_APP_CERTBOT_WEBROOT=/opt/meal-app-certbot
```

### 2. Create host ACME directory

```bash
sudo mkdir -p /opt/meal-app-certbot/.well-known/acme-challenge
sudo chown -R mealapp:mealapp /opt/meal-app-certbot
```

### 3. Recreate only the proxy (picks up the new volume)

```bash
cd /opt/meal-app
docker compose up -d --force-recreate --no-deps proxy
docker compose ps proxy
```

Confirm the mount:

```bash
docker inspect mealapp-proxy --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
# Expect: /opt/meal-app-certbot -> /var/www/certbot
```

### 4. Test challenge file over HTTP

```bash
echo ok-challenge > /opt/meal-app-certbot/.well-known/acme-challenge/ping-test
curl -sS http://127.0.0.1/.well-known/acme-challenge/ping-test
curl -sS http://mealapp.ru/.well-known/acme-challenge/ping-test
# Both must print: ok-challenge
rm -f /opt/meal-app-certbot/.well-known/acme-challenge/ping-test
```

Only when that works, run host Certbot with webroot (example — run as root on VPS):

```bash
sudo certbot certonly --webroot \
  -w /opt/meal-app-certbot \
  -d mealapp.ru -d www.mealapp.ru \
  --agree-tos -m your-email@example.com
```

### 5. Enable TLS (separate follow-up — not in this step)

After certificates exist under `/etc/letsencrypt`:

1. Add TLS `server` block / mount `/etc/letsencrypt` into proxy.
2. Publish `443:443` in Compose.
3. Set `ALLOWED_ORIGINS=https://mealapp.ru,https://www.mealapp.ru` and restart.
4. BotFather Mini App URL → `https://mealapp.ru`.

Do **not** enable HTTPS until step 4 (challenge test) succeeds.

---

## Timeouts

| Layer | Value |
|-------|-------|
| Frontend axios | 300000 ms |
| Edge nginx `proxy_*_timeout` | 300s |

---

## Security checklist

- [ ] `.env` mode `600`, owned by `mealapp`, never in git
- [ ] `ALLOW_DEV_AUTH=false`, `ENVIRONMENT=production`
- [ ] `/api/health` shows `dev_tools: false`
- [ ] Backend `:8000` not on host
- [ ] No localhost in production frontend bundle / CORS
- [ ] HTTPS before inviting Telegram users

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
- TLS must be finished on the VPS before production Mini App use.
