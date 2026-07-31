# Security

## Telegram Mini App authentication

### Frontend

- Official SDK: `https://telegram.org/js/telegram-web-app.js` (loaded in `index.html` before React).
- Each protected API request sends `Authorization: tma <initData>`.
- `initData` is read from `Telegram.WebApp.initData` on every request.
- **Never** store `initData`, `hash`, or auth headers in `localStorage`.
- **Never** log `initData` or Authorization header values.

### Backend

- `backend/telegram_auth.py` validates initData using Telegram's HMAC-SHA256 algorithm.
- Signature comparison uses `hmac.compare_digest`.
- `auth_date` must be recent (default max age: 3600 seconds).
- `user_id` is taken **only** from verified initData — request body `user_id` is not accepted.

### Development mode

Set in `backend/.env`:

```env
ALLOW_DEV_AUTH=true
DEV_TELEGRAM_USER_ID=1
```

When enabled, requests without `Authorization` are accepted as the dev user. A warning is logged at startup.

**Disable before production:**

```env
ALLOW_DEV_AUTH=false
TELEGRAM_BOT_TOKEN=<from @BotFather>
```

### CORS

Origins are configured via `ALLOWED_ORIGINS` (comma-separated). Default for local dev:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Do not use `allow_origins=["*"]` with `allow_credentials=True` in production.

### Logging policy

**Do not log:**

- Full `Authorization` header
- `initData` string
- `hash` value
- Bot token
- Full user JSON from initData

**Safe to log after successful auth:**

- `user_id` (integer)
- Internal auth failure reason codes (e.g. `expired initData`, `invalid signature`)

### Production deploy checklist

1. Set `TELEGRAM_BOT_TOKEN` from @BotFather.
2. Set `ALLOW_DEV_AUTH=false`.
3. Set `ALLOWED_ORIGINS` to your production frontend URL(s).
4. Ensure HTTPS for both frontend and backend.
5. Register the Mini App URL in BotFather.
6. Verify `/api/health` returns `auth_mode: "telegram"` and `telegram_auth_configured: true`.
