🍽 Meal Planner Web App (Контекст для ИИ-агентов)
Архитектура
Frontend: React + TypeScript + Vite + TailwindCSS. Папка webapp/.
Backend: Python + FastAPI. Папка backend/.
AI: Claude 3.5 Sonnet (через Anthropic API). Промпты и логика в backend/claude_service.py.
База данных пока НЕ используется (всё в памяти/словарях Python).
Правила для Frontend (React)
Используй TailwindCSS для стилей. НЕ используй обычный CSS или styled-components.
Используй переменные темы Telegram: var(--tg-theme-bg-color), var(--tg-theme-button-color) и т.д.
Запросы к бэкенду делай ТОЛЬКО через файл src/api.ts (на основе Axios).
Не используй alert() или prompt(). Только визуальные состояния (тосты, красные рамки).
Компоненты должны быть адаптивными (мобильная верстка приоритетна).
API Эндпоинты (Backend)
Все запросы возвращают JSON.

POST /api/generate-menu — Принимает {days, budget, proteins, goal...}, возвращает полный план питания (меню, рецепты, корзину).
POST /api/get-profile — Возвращает настройки пользователя по умолчанию.
GET /api/health — Проверка жизни сервера.
Структура ответа Claude (для верстки)
Ответ от /api/generate-menu содержит объект:

summary (string) — краткое описание.
total_cost (number) — общая сумма.
days_plan (array) — массив дней [{day: "День 1", breakfast: "...", lunch: "...", dinner: "..."}].
recipes (array) — массив рецептов [{name, emoji, cook_time, kbju, ingredients: [{name, amount}], steps: [string]}].
basket (array) — корзина [{category: "Мясо", items: [{name, weight, price}]}].
Теперь, когда ты даешь задачу агенту, ты просто пишешь: "Прочитай CONTEXT.md и сделай..."