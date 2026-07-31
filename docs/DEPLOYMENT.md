# Deployment Guide — MealApp closed-beta (VPS Ubuntu 24.04 + Docker Compose)

This guide deploys **frontend + backend behind one Nginx reverse proxy** on
`mealapp.ru` / `www.mealapp.ru`. Backend port **8000 is not published** on the host.

Business logic (Strategy, Decision Engine, Learned Preferences, Basket Engine,
API contracts) is unchanged by this stack.

## Architecture

```
Internet
   │
   ▼
:80  mealapp-proxy (nginx)
   ├── /          → mealapp-webapp:80   (Vite static SPA)
   └── /api/      → mealapp-backend:8000 (FastAPI)
                         │
                         ▼
                   volume → /data/app.db  (SQLite)
```

| Service   | Public ports | Notes                                      |
|-----------|--------------|--------------------------------------------|
| `proxy`   | `80`         | Edge reverse proxy; Certbot-ready for 443  |
| `webapp`  | none         | Internal only                              |
| `backend` | none         | Internal only; SQLite on persistent volume |

Telegram bot (`bot/`) remains a **separate host process** for now (not in Compose).

---

## Prerequisites (VPS)

- Ubuntu 24.04
- Docker Engine + Docker Compose plugin
- DNS: `mealapp.ru` and `www.mealapp.ru` → VPS public IP
- Domains pointing at the VPS before users open the Mini App

```bash
sudo mkdir -p /opt/meal-app /opt/meal-app-data
sudo chown "$USER:$USER" /opt/meal-app /opt/meal-app-data
cd /opt/meal-app
git clone https://github.com/fesquwork-dotcom/meal-app.git .
# or: git pull if already cloned
```

---

## 1. Create production `.env`

```bash
cd /opt/meal-app
cp .env.example .env
chmod 600 .env
nano .env   # or vim
```

### Required variables

| Variable | Example / notes |
|----------|-----------------|
| `TELEGRAM_BOT_TOKEN` | From BotFather (same token for backend verification) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `STRATEGY_PREVIEW_SECRET` | Random secret, 32+ bytes (`openssl rand -hex 32`) |
| `ENVIRONMENT` | `production` |
| `ALLOW_DEV_AUTH` | `false` |
| `DATABASE_PATH` | `/data/app.db` |
| `ALLOWED_ORIGINS` | `https://mealapp.ru,https://www.mealapp.ru` |
| `MEAL_APP_DATA_PATH` | `/opt/meal-app-data` |
| `VITE_API_BASE_URL` | `same-origin` (browser → `/api` via proxy) |
| `ANTHROPIC_TRUST_ENV` | `false` in production (do not inherit host proxies) |

### Explicitly do **not** set in production

- `ALLOW_DEV_AUTH=true`
- `DEV_TELEGRAM_USER_ID`
- `VITE_ENABLE_DIAGNOSTICS=true`
- localhost origins in `ALLOWED_ORIGINS`

Until TLS is enabled, browsers may still use `http://mealapp.ru`. For HTTP-only
closed beta, temporarily set:

```env
ALLOWED_ORIGINS=http://mealapp.ru,http://www.mealapp.ru
```

Switch to `https://…` as soon as Certbot is configured. Telegram Mini Apps
require **HTTPS** for real users.

### `ANTHROPIC_TRUST_ENV`

| Value | Behavior |
|-------|----------|
| `false` (default in Compose) | httpx does **not** use `HTTP_PROXY` / `HTTPS_PROXY` |
| `true` | httpx honors proxy env vars (VPN / corporate proxy only) |

---

## 2. Validate Compose config

```bash
cd /opt/meal-app
docker compose config
```

Confirm:

- `backend` has no `ports:` mapping for 8000
- `proxy` publishes `80:80` only
- volume bind is `/opt/meal-app-data:/data`

---

## 3. Build images

```bash
docker compose build
```

Frontend build uses `VITE_API_BASE_URL=same-origin` and
`VITE_ENABLE_DIAGNOSTICS=false`. Localhost API URLs fail the image build.

---

## 4. First start

```bash
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

Logs must not contain API keys or bot tokens. If you see secrets, rotate them
immediately and scrub logs.

---

## 6. Health checks

```bash
curl -sS http://127.0.0.1/api/health
curl -sS http://127.0.0.1/api/ready
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1/
```

Expect:

- `/api/health` → `status: ok`, `auth_mode: telegram`, `dev_tools: false`
- `/api/ready` → `status: ready` (or `degraded` if Claude key/network issue)
- `/` → HTTP 200 (SPA)

Confirm backend is **not** on the public interface:

```bash
ss -lntp | grep 8000 || echo "OK: 8000 not listening on host"
curl -sS --connect-timeout 2 http://127.0.0.1:8000/api/health && echo "UNEXPECTED: backend exposed" || echo "OK: backend not reachable on host :8000"
```

---

## 7. BotFather + Telegram bot

1. BotFather → Menu Button / Web App → `https://mealapp.ru` (after TLS)
2. On the VPS (separate from Compose):

```bash
cd /opt/meal-app/bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# BOT_TOKEN=…  MINI_APP_URL=https://mealapp.ru  BOT_ENVIRONMENT=production
python main.py
```

Prefer a systemd unit for the bot in a later ops pass.

---

## 8. Update (git pull)

```bash
cd /opt/meal-app
git fetch origin
git checkout main   # or master, matching the default branch
git pull --ff-only
docker compose build
docker compose up -d
docker compose ps
curl -sS http://127.0.0.1/api/health
```

SQLite under `/opt/meal-app-data` is preserved across rebuilds.

---

## 9. Safe rollback

```bash
cd /opt/meal-app
# Record current revision
git rev-parse HEAD

# Roll code back (example: previous commit)
git fetch origin
git checkout <previous-commit-or-tag>
docker compose build
docker compose up -d
```

If the DB schema changed forward-only, restore SQLite from backup **before**
starting the rolled-back containers (see below).

---

## 10. SQLite backup

```bash
sudo systemctl stop docker 2>/dev/null || true   # optional; prefer compose stop
cd /opt/meal-app
docker compose stop backend
TS=$(date -u +%Y%m%dT%H%M%SZ)
sudo cp -a /opt/meal-app-data/app.db "/opt/meal-app-data/app.db.bak-$TS"
# Online-safe alternative while backend is running (SQLite backup API):
# sqlite3 /opt/meal-app-data/app.db ".backup '/opt/meal-app-data/app.db.bak-$TS'"
docker compose start backend
```

Keep backups off the VPS when possible (`scp` to a secure host).

---

## 11. SQLite restore

```bash
cd /opt/meal-app
docker compose stop backend
sudo cp -a /opt/meal-app-data/app.db "/opt/meal-app-data/app.db.pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
sudo cp -a /opt/meal-app-data/app.db.bak-YYYYMMDDTHHMMSSZ /opt/meal-app-data/app.db
sudo chown 1000:1000 /opt/meal-app-data/app.db   # appuser in image; adjust if needed
docker compose start backend
curl -sS http://127.0.0.1/api/ready
```

---

## 12. Stop the application

```bash
cd /opt/meal-app
docker compose down
# Data in /opt/meal-app-data is kept. To remove containers + network only:
# docker compose down   # volumes/bind mounts are not deleted for bind paths
```

---

## HTTPS (next stage — Certbot)

HTTP-only is fine for infrastructure smoke tests. Telegram Mini Apps need HTTPS.

Sketch (after DNS works):

```bash
# Install certbot nginx plugin on the host, then either:
# 1) temporarily expose a host nginx for ACME, or
# 2) add a certbot companion / mount /etc/letsencrypt into mealapp-proxy
#
# After certificates exist, enable 443 in docker-compose.yml and add an ssl
# server block (or let certbot emit one) pointing to the same upstreams.
sudo apt install -y certbot
# Prefer documenting the exact ACME flow chosen for this VPS in an ops runbook.
```

`deploy/nginx/default.conf` is intentionally HTTP-only and Certbot-compatible
(standard `server_name`, no conflicting SSL yet).

---

## Timeouts

| Layer | Value |
|-------|-------|
| Frontend axios | `300000` ms (5 min) |
| Edge nginx `proxy_*_timeout` | `300s` |
| Uvicorn | no max request duration; does not cancel generation |

---

## Security checklist

- [ ] `.env` mode `600`, not in git
- [ ] `ALLOW_DEV_AUTH=false`, `ENVIRONMENT=production`
- [ ] `/api/dev/*` returns 404 (`dev_tools: false` on `/api/health`)
- [ ] Backend `:8000` not published
- [ ] No localhost in production frontend bundle
- [ ] CORS origins match the real Mini App URL scheme/host
- [ ] SQLite backups encrypted / access-controlled

---

## Troubleshooting

### 401 Telegram authentication

- Open from Telegram bot button (initData required)
- `TELEGRAM_BOT_TOKEN` must match the bot that opened the Mini App

### CORS errors

- Align `ALLOWED_ORIGINS` with exact scheme + host (`https://mealapp.ru`)

### Generation aborts ~60–120s

- Confirm edge nginx timeouts are 300s
- Confirm no extra host proxy in front with a shorter timeout

### Blank SPA

- `docker compose logs webapp proxy`
- Confirm `VITE_API_BASE_URL=same-origin` at build time
- Open browser network tab: `/api/health` should be same-origin

### SQLite permission denied

- Ensure `/opt/meal-app-data` is writable by container user (`appuser`)
- `sudo chown -R 1000:1000 /opt/meal-app-data` (UID matches image `appuser`)

---

## Content Security Policy

CSP is **not** set. The SPA loads `https://telegram.org/js/telegram-web-app.js`.
Treat missing CSP as a known closed-beta limitation.

---

## Legacy notes

Older split-host deploys (public `:8000` + separate frontend URL) are
superseded by this Compose stack. Prefer `same-origin` + edge `/api` proxy.
