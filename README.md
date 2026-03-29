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

2. Создайте `.env` с переменной `DATABASE_URL`.

Пример:
```env
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/ai_web_db
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

## реализовано

- добавлена сущность `ChatSession`
- реализована связь `User -> ChatSession -> ChatHistory`
- доработан `POST /chat`
- доработан `POST /chat/stream`
- добавлены эндпоинты для создания и получения чат-сессий
- обновлены Pydantic-схемы
- изменения схемы базы данных оформлены через Alembic

## основные эндпоинты

- `POST /users/{user_id}/sessions`
- `GET /users/{user_id}/sessions`
- `GET /users/{user_id}/sessions/{session_id}`
- `POST /chat`
- `POST /chat/stream`
