🍽 Meal Planner Web App (Контекст для ИИ-агентов)

Архитектура
Frontend: React + TypeScript + Vite + TailwindCSS. Папка webapp/.
Backend: Python + FastAPI. Папка backend/.
AI: Claude (модель задаётся через `CLAUDE_MODEL` в `backend/config.py`; default `claude-sonnet-4-6`). Промпты и логика в `backend/claude_service.py`.
База данных: SQLite через aiosqlite. Файл backend/app.db, работа с ней — в backend/database.py. Таблица profiles хранит последние параметры запроса пользователя (upsert по user_id), включая `meal_types` (JSON string).

Правила для Frontend (React)
Используй TailwindCSS для стилей. НЕ используй обычный CSS или styled-components.
Используй переменные темы Telegram: var(--tg-theme-bg-color), var(--tg-theme-button-color) и т.д.
Запросы к бэкенду делай ТОЛЬКО через файл src/api.ts (на основе Axios).
Не используй alert() или prompt(). Только визуальные состояния (тосты, красные рамки).
Компоненты должны быть адаптивными (мобильная верстка приоритетна).

API Эндпоинты (Backend)
Все запросы возвращают JSON.

POST /api/generate-menu — Принимает настройки меню (без user_id), включая `meal_types: string[]` и deprecated `meals_per_day`. Возвращает полный план питания. Требует Authorization: tma <initData>. После успешной генерации параметры сохраняются в БД для user_id из проверенного Telegram initData.
POST /api/get-profile — Возвращает `{profile: {...}}` для текущего Telegram-пользователя, включая `meal_types` и вычисленный `meals_per_day`. Требует Authorization: tma <initData>.
GET /api/health — Публичная проверка жизни сервера. Возвращает claude_model, auth_mode, telegram_auth_configured.

Telegram Authentication
Frontend подключает https://telegram.org/js/telegram-web-app.js и отправляет в каждый защищённый запрос заголовок Authorization: tma <initData>.
initData берётся из Telegram.WebApp.initData при каждом запросе. Нельзя сохранять initData в localStorage.
Backend (backend/telegram_auth.py) проверяет подпись initData по алгоритму Telegram Mini Apps (HMAC-SHA256, compare_digest).
user_id для БД и бизнес-логики берётся только из проверенного initData.user — поле user_id в теле запроса удалено.
Локальная разработка: ALLOW_DEV_AUTH=true в .env разрешает запросы без Authorization с DEV_TELEGRAM_USER_ID.
Production: ALLOW_DEV_AUTH=false, TELEGRAM_BOT_TOKEN обязателен.
initData имеет ограниченный срок жизни (TELEGRAM_INIT_DATA_MAX_AGE_SECONDS, default 3600).

Структура ответа Claude (для верстки)
Ответ от /api/generate-menu содержит объект:

summary (string) — краткое описание.
total_cost (number) — после BasketEngine rebuild = shopping_cost (покупная корзина).
  До rebuild Claude-поле model_total — только диагностика.
shopping_cost / recipe_cost / budget_usage_percent — additive wire fields (Sprint 10.5+).
  Авторитетный weekly budget metric: shopping_cost (Sprint 10.8).
days_plan (array) — массив дней. Основной контракт: `{day, meals: [{type, recipe_name}]}`. Для обратной совместимости также возвращаются `breakfast`, `lunch`, `dinner`.
recipes (array) — массив рецептов [{name, emoji, cook_time, kbju, ingredients: [{name, amount}], steps: [string]}].
basket (array) — корзина [{category: "Мясо", items: [{name, weight, price}]}].

Menu Generation Reliability
Claude response проходит серверный pipeline перед отдачей клиенту:

1. extract_json_object() — строгое извлечение одного JSON-объекта (без repair-эвристик).
2. MenuPlan (Pydantic) — структурная валидация полей, типов, непустых строк, price >= 0.
3. validate_menu_plan() — бизнес-правила: meal_types, бюджет, meal↔recipe, аллергии, cooktime, дубликаты, корзина.

Бюджет (request.budget) — на весь период планирования, tolerance = 0.
total_cost сверяется с суммой basket item.price (±1 ₽).
Ошибки (error) блокируют ответ → HTTP 502 с общим сообщением пользователю.
Предупреждения (warning) логируются, но не блокируют ответ.
Frontend не получает невалидный MenuPlan.

Подробности и коды ошибок: docs/MENU_VALIDATION.md

Прогресс задач
[x] 1.1 — Подключение SQLite (aiosqlite) для хранения профилей вместо in-memory словаря.
[x] Валидация Telegram initData на бэкенде.
[x] Подключение Telegram Web App SDK на фронтенде (telegram-web-app.js).
[ ] React-компонент карточки рецепта с раскрывающимися шагами.
[ ] Адаптивная вёрстка под мобильный Telegram (Tailwind).
[ ] Деплой backend + frontend.

Теперь, когда ты даешь задачу агенту, ты просто пишешь: "Прочитай CONTEXT.md и сделай..."
