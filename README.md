## запуск

1. Запустите PostgreSQL.

Пример через Docker:
```bash
docker run -d -p 5433:5432 \
  -e POSTGRES_PASSWORD=root \
  -e POSTGRES_DB=ai_web_db \
  -e POSTGRES_USER=postgres \
  postgres:16.9-alpine
```

Пример локально через Homebrew:
```bash
brew install postgresql@16
brew services start postgresql@16
createdb ai_web_db
```

2. Создайте `.env` на основе `.env-example`.

Для mock-режима (без реальной модели):
```env
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/ai_web_db
LLM_MODE=mock
```

Для real-режима (с реальной LLM через OpenRouter):
```env
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/ai_web_db
LLM_MODE=real
LLM_API_KEY=your-openrouter-api-key
LLM_MODEL=google/gemma-3-1b-it:free
LLM_BASE_URL=https://openrouter.ai/api/v1
```

3. Установите зависимости:
```bash
uv sync
```

4. Примените миграции:
```bash
uv run alembic upgrade head
```

5. Запустите API:
```bash
uv run uvicorn app.main:app --reload --port 8000
```

6. Swagger:
```text
http://127.0.0.1:8000/docs
```

## выбор провайдера и модели

- **Провайдер:** [OpenRouter](https://openrouter.ai/) — агрегатор LLM-провайдеров с OpenAI-совместимым API
- **Модель по умолчанию:** `google/gemma-3-1b-it:free` — бесплатная модель Google Gemma 3 1B
- Можно использовать любую модель, доступную на OpenRouter, указав её в `LLM_MODEL`

## архитектура LLM-слоя

```
LLMInterface (абстрактный класс)
├── MockLLM          — тестовый режим, эхо-ответы
└── OpenRouterLLM    — реальная LLM через OpenRouter API
```

- Переключение между режимами через переменную `LLM_MODE` в `.env`
- Роуты `/chat` и `/chat/stream` работают с единым интерфейсом `LLMInterface`
- Роуты не зависят от конкретного провайдера
- В истории (`response_metadata`) сохраняется имя использованной модели

## переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `DATABASE_URL` | да | Строка подключения к PostgreSQL |
| `LLM_MODE` | нет | Режим работы: `mock` (по умолчанию) или `real` |
| `LLM_API_KEY` | при `real` | API-ключ OpenRouter |
| `LLM_MODEL` | нет | Название модели (по умолчанию `google/gemma-3-1b-it:free`) |
| `LLM_BASE_URL` | нет | URL провайдера (по умолчанию `https://openrouter.ai/api/v1`) |

## реализовано

### ДЗ 1 — чат-сессии
- добавлена сущность `ChatSession`
- реализована связь `User -> ChatSession -> ChatHistory`
- доработан `POST /chat`
- доработан `POST /chat/stream`
- добавлены эндпоинты для создания и получения чат-сессий
- обновлены Pydantic-схемы
- изменения схемы базы данных оформлены через Alembic

### ДЗ 2 — интеграция реальной LLM
- добавлена поддержка реальной LLM через OpenRouter API
- MockLLM сохранён как fallback-режим
- переключение между mock и real через `.env` (`LLM_MODE`)
- выделен единый интерфейс `LLMInterface` — роуты не зависят от провайдера
- `/chat` и `/chat/stream` работают с реальной моделью
- в истории сохраняется информация об использованной модели
- ошибки провайдера обрабатываются корректно (HTTP-ошибки, таймауты)
- обновлены конфигурация, `.env-example` и `README.md`

## основные эндпоинты

- `POST /users/{user_id}/sessions`
- `GET /users/{user_id}/sessions`
- `GET /users/{user_id}/sessions/{session_id}`
- `POST /chat`
- `POST /chat/stream`
