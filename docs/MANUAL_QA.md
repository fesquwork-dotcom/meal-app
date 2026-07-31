# Manual QA — Meal App (Sprint 9.5)

Этот документ — единая инструкция для ручного тестирования после Phase 9.

## Быстрый старт

### Основной способ (раздельно — надёжнее)

```bash
# Terminal 1 — backend
cd backend
copy .env.example .env
# В .env для локального QA:
# ENVIRONMENT=development
# ALLOW_DEV_AUTH=true
# DEV_TELEGRAM_USER_ID=1
# ADAPTIVE_PREFERENCES=true
# ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
# ANTHROPIC_API_KEY=  (можно пустым для read-only сценариев)
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd webapp
copy .env.example .env.local
# VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev
```

Открыть: http://localhost:5173  
Diagnostics: http://localhost:5173/diagnostics

### Проверка готовности

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/ready
```

- `ready` + Claude → генерация меню доступна
- `degraded` без Claude → Profile / History / Learned Preferences доступны
- `not_ready` → БД или auth не готовы

## Environment

См. `backend/.env.example` (Required / Optional / Development / Production).

**Важно:** `ENVIRONMENT=production` + `ALLOW_DEV_AUTH=true` → backend не стартует.

## Dev QA tools (только development)

На `/diagnostics` при `dev_tools=true`:

- Сбросить тестовую историю (`history_only`)
- Полностью сбросить тестового пользователя (`full_user`)
- Загрузить Phase 9 сценарии

API:

- `POST /api/dev/reset-current-user` `{ "confirm": "RESET", "mode": "history_only"|"full_user" }`
- `POST /api/dev/load-qa-scenario` `{ "scenario": "<allowlisted>" }`
- `GET /api/dev/diagnostics`

Reset всегда действует только на **текущего** authenticated user (dev fallback ID).

## QA scenarios

| Scenario | Что даёт |
|----------|----------|
| `fresh_user` | Пустой пользователь |
| `profile_ready` | Profile без меню |
| `active_week` | Active Strategy + MenuPlan |
| `completed_history` | Несколько завершённых планов |
| `learning_candidate` | Кандидат Learned Preference |
| `learned_preference_active` | Active preference + applied snapshot |
| `learned_preference_insufficient` | 1 applied plan |
| `learned_preference_emerging` | 2–3 positive plans |
| `learned_preference_effective` | 4+ positive |
| `learned_preference_ineffective` | 4+ high replacement + review |
| `review_dismissed` | Review скрыт после keep |
| `review_new_generation` | Новая когорта → review снова |
| `legacy_partial_data` | Legacy strategy без snapshot |

Fixtures **не вызывают Claude** и используют якорь даты `2026-07-13`.

## Smoke (авто)

```bash
cd backend
python -m pytest -q -m smoke

cd ../webapp
npm test -- --run
npm run lint
npm run build
```

## Структура сценария

```text
ID
Название
Начальное состояние
Шаги
Ожидаемый результат
Что не должно измениться
Диагностические данные при ошибке
Статус
Комментарий
```

---

## P0 — запуск

### QA-001 — Первый запуск
- Начальное: `fresh_user` или чистая БД
- Шаги: открыть app → Profile → сохранить → reload
- Ожидается: Profile сохранён, нет console errors
- Не должно: silent failure

### QA-002 — Backend недоступен
- Остановить backend → открыть app
- Ожидается: controlled offline / Retry, нет бесконечного spinner

### QA-003 — Diagnostics
- Открыть `/diagnostics`
- Проверить health, ready, copy bundle, режим разработки

---

## P0 — меню

### QA-010 — Preview
Profile → generate flow → Preview. Без duplicate requests.

### QA-011 — Generate
(Нужен `ANTHROPIC_API_KEY`) Меню, Strategy, Basket, Today/Week.

### QA-012 — Reload
Текущий план сохраняется.

### QA-013 — Replace meal
Меняется только выбранный meal; Strategy immutable.

---

## P0 — Profile invalidation

### QA-020 / QA-021 / QA-022
Preview отражает Profile; stale после изменения; current MenuPlan не меняется.

---

## P0 — Learned Preferences

### QA-030 Candidate
Fixture `learning_candidate` → карточка кандидата.

### QA-031 Accept
Active + planning effect; current MenuPlan неизменен; Preview сброшен.

### QA-032 Applied next plan
Следующий Preview/Strategy показывает Learned source; Profile priority.

### QA-033 Revoke
Future Preview без preference; current plan остаётся.

---

## P0 — Effectiveness / Review

### QA-040…QA-046
Fixtures: insufficient / emerging / effective / ineffective / review_dismissed / review_new_generation / revoke from review.

Keep across reload: review скрыт.  
New cohort: review снова.  
Accept/revoke/dismiss **не** меняют current MenuPlan.

---

## P1 — History / Insights / failures

См. полный список QA-050…QA-066 в Sprint 9.5 spec.  
При ошибке: controlled UI, Retry, Correlation ID из diagnostics.

## Severity

См. `docs/BUG_REPORT_TEMPLATE.md`.

## Блоки ручного прогона

1. Чистый первый запуск  
2. Создание и замена меню  
3. Полный цикл Learned Preference  
4. Ошибки и восстановление  
