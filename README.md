# Meal App

Локальный запуск и ручное QA: см. **[docs/MANUAL_QA.md](docs/MANUAL_QA.md)**.

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

## Tests

```bash
cd backend && python -m pytest -q && python -m pytest -q -m smoke
cd webapp && npm test -- --run && npm run lint && npm run build
```

## Docs

- [Manual QA](docs/MANUAL_QA.md)
- [Bug report template](docs/BUG_REPORT_TEMPLATE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Security](docs/SECURITY.md)
