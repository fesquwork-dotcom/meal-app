# Meal App

Production (VPS / Docker Compose): **[DEPLOYMENT.md](DEPLOYMENT.md)** → [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

Локальный запуск и ручное QA: **[docs/MANUAL_QA.md](docs/MANUAL_QA.md)**.

## Quick start (local QA)

```bash
# Backend
cd backend
cp .env.example .env   # Windows: copy .env.example .env
# Set ENVIRONMENT=development, ALLOW_DEV_AUTH=true, ADAPTIVE_PREFERENCES=true
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd webapp
cp .env.example .env.local
# VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev
```

- App: http://localhost:5173  
- Diagnostics: http://localhost:5173/diagnostics  
- Health: http://localhost:8000/api/health  
- Ready: http://localhost:8000/api/ready  

## Production stack (summary)

```bash
cp .env.example .env   # fill secrets; MEAL_APP_DATA_PATH=/opt/meal-app-data
docker compose config
docker compose build
docker compose up -d
curl -sS http://127.0.0.1/api/health
```

Only host port **80** is published. Backend `:8000` stays on the internal Docker network.

## Tests

```bash
cd backend && python -m pytest -q && python -m pytest -q -m smoke
cd webapp && npm test -- --run && npm run lint && npm run build
```

## Docs

- [Deployment](docs/DEPLOYMENT.md)
- [Manual QA](docs/MANUAL_QA.md)
- [Bug report template](docs/BUG_REPORT_TEMPLATE.md)
- [Security](docs/SECURITY.md)
