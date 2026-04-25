# AI Web — итоговый проект «Методы и инструменты искусственного интеллекта»

Production-ready ML-сервис: чат с LLM, очередь задач, мониторинг, реверс-прокси, мини-классификатор намерений на ONNX. Запускается одной командой.

---

## 🚀 Быстрый старт

```bash
# 1. Скопируй конфиг
cp .env.example .env
# (опционально) пропиши свой OpenRouter ключ:
#   LLM_MODE=real
#   LLM_API_KEY=sk-or-v1-...
# Без ключа сервис работает в режиме MOCK.

# 2. Поднимаем всё одной командой
docker compose up --build -d

# 3. (опционально) обучаем и экспортируем свою ONNX-модель внутри контейнера
docker compose exec api_a python scripts/train_local_model.py
docker compose restart api_a api_b

# 4. Открываем
#   http://localhost/                 — Streamlit UI
#   http://localhost/api/docs         — Swagger
#   http://localhost/api/health       — health check
#   http://localhost/grafana/         — Grafana (admin / admin)
#   http://localhost/prometheus/      — Prometheus
```

---

## 🏗️ Архитектура

```
                            ┌─────────────────┐
                            │   Browser :80   │
                            └────────┬────────┘
                                     │ HTTP
                            ┌────────▼────────┐
                            │ NGINX (reverse  │
                            │ proxy + LB)     │
                            │ rate-limit 5/m  │
                            └─┬─────────┬─────┘
            /api/*  ┌─────────┘         └──────────┐  /
                    ▼                              ▼
            ┌────────────────┐              ┌──────────────┐
            │   API api_a    │  ◀── least_  │  Streamlit   │
            │   (FastAPI)    │     conn ──▶ │     UI       │
            ├────────────────┤              └──────┬───────┘
            │   API api_b    │                     │ REST
            │   (FastAPI)    │ ◀───────────────────┘
            └─┬───┬──────┬───┘
              │   │      │
       ┌──────┘   │      └──────────┐
       ▼          ▼                 ▼
  ┌─────────┐ ┌────────┐      ┌──────────┐
  │Postgres │ │ Redis  │      │  Celery  │
  │         │ │ broker │ ◀────│  Workers │ × 2
  │  ACID   │ │+ pub/sub│     │ (Model-  │
  │  + JSONB│ └────────┘      │ in-Worker)│
  └─────────┘                 └──────────┘
       ▲
       │  Alembic migrations
       │  (одноразовый сервис `migrate`)

  Мониторинг:  api_a/api_b → Prometheus → Grafana

  Сети:
   ─ frontend_net : nginx ↔ ui ↔ api
   ─ backend_net  : api ↔ postgres ↔ redis ↔ worker   (UI и nginx сюда не лезут)
   ─ monitoring_net: prometheus ↔ grafana ↔ api
```

### Что где живёт

| Каталог | Назначение |
|---|---|
| `app/core/` | конфиг, логирование, lifespan, кастомные ошибки |
| `app/db/` | SQLAlchemy 2.0 (async) — Base, session, models |
| `app/schemas/` | Pydantic-схемы Request/Response |
| `app/ml/` | LLM-интерфейс (Mock/OpenRouter) + локальный ONNX-классификатор |
| `app/tasks/` | Celery: очередь задач, инференс LLM в воркере |
| `app/api/` | FastAPI роуты: users, sessions, chat, tasks, classify, health |
| `app/main.py` | сборка приложения (lifespan + middleware + Prometheus) |
| `alembic/` | миграции |
| `ui/` | Streamlit-фронт (4 таба, Plotly-графики) |
| `scripts/train_local_model.py` | обучение TF-IDF+LogReg → ONNX |
| `docker/nginx/` | конфиги Nginx (rate-limit, LB, маршрутизация) |
| `prometheus/`, `grafana/` | конфиги и provisioning дашбордов |

---

## 🔌 API endpoints (cURL)

База: `http://localhost/api`. Swagger: `http://localhost/api/docs`.

```bash
# ── Health ─────────────────────────────────────────────
curl http://localhost/api/health

# ── Users ──────────────────────────────────────────────
curl -X POST http://localhost/api/users \
  -H "Content-Type: application/json" \
  -d '{"name":"caesar","email":"caesar@example.com"}'

curl http://localhost/api/users

# ── Sessions ───────────────────────────────────────────
curl -X POST http://localhost/api/users/1/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"Brainstorm thesis"}'

curl http://localhost/api/users/1/sessions
curl http://localhost/api/users/1/sessions/1/messages

# ── Sync chat ──────────────────────────────────────────
curl -X POST http://localhost/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":1,"prompt":"Say hi","creativity":0.7,"max_new_tokens":64}'

# ── Async chat (Celery queue) — возвращает 202 + task_id ──
curl -X POST http://localhost/api/chat/async \
  -H "Content-Type: application/json" \
  -d '{"session_id":1,"prompt":"Write a 200-word essay on attention.","creativity":0.6,"max_new_tokens":256}'

# ── Polling статуса ────────────────────────────────────
curl http://localhost/api/tasks/<task_id>

# ── WebSocket-стрим статуса ────────────────────────────
# wscat -c ws://localhost/api/ws/tasks/<task_id>

# ── Классификация намерения (своя ONNX-модель) ────────
curl -X POST http://localhost/api/classify \
  -H "Content-Type: application/json" \
  -d '{"text":"please summarize this article"}'
```

---

## 🛠 Стек

- **API**: FastAPI + Uvicorn (ASGI), Pydantic v2
- **DB**: PostgreSQL 16 + SQLAlchemy 2.0 (async, asyncpg) + Alembic
- **Очередь**: Celery 5 + Redis (broker, backend, Pub/Sub для WebSocket)
- **LLM**: OpenRouter (Gemma 3 1B free), Mock — fallback. Через единый `LLMInterface`
- **Своя модель**: TF-IDF + LogisticRegression → ONNX (sklearn → skl2onnx → onnxruntime)
- **UI**: Streamlit + httpx + Plotly
- **Reverse proxy**: Nginx (rate-limit 5 req/min, LB `least_conn` между api_a/api_b)
- **Мониторинг**: prometheus-fastapi-instrumentator + Prometheus + Grafana (provisioning)
- **Менеджер пакетов**: uv (быстрая сборка образов)
- **Оркестрация**: Docker Compose (3 изолированные сети, healthchecks, `depends_on: service_healthy`)

---

## 🧪 Чек-лист соответствия требованиям

Каждый пункт помечен в коде комментарием с названием раздела (например `# Логирование`).

### 1. FastAPI бэкенд — 6 + 5 (звёздочки)
- ✅ **[2] Lifespan** (`app/core/lifespan.py`) — БД, Redis, LLM, ONNX-модель грузятся ОДИН раз при старте (Model-in-App).
- ✅ **(4*) Celery + Redis** (`app/tasks/`, эндпоинт `POST /api/chat/async` → 202).
- ✅ **(1*) WebSocket-проверка статуса** (`/api/ws/tasks/{id}` через Redis Pub/Sub).
- ✅ **[2] Pydantic-валидация** (`app/schemas/schemas.py`): `Field(ge=0.0, le=1.0)` для `creativity`, examples, descriptions.
- ✅ **[2] Кастомные обработчики ошибок** (`app/core/errors.py`): 400/404/409/422/500/503 + понятный JSON.

### 2. ML сервис — 6 + 7 (звёздочки)
- ✅ **[2] Изоляция ML-логики** — `LLMInterface` (`app/ml/interface.py`), реализации `MockLLM`, `OpenRouterLLM` через `factory.py`.
- ✅ **[2] Управление ресурсами** — `LLM_MAX_NEW_TOKENS` в settings, передаётся в каждый `generate()`; обрезка длинного prompt в Mock; ограничение потоков ONNX (`intra_op_num_threads=2`).
- ✅ **[2] Логирование** (`app/core/logging.py`) — JSON-логи + `log_duration` контекст-менеджер для всех этапов (db, llm, onnx).
- ✅ **(5*) Своя модель** — `scripts/train_local_model.py` (TF-IDF + LogReg → ONNX); описание процесса в шапке файла.
- ✅ **(2*) Оптимизация инференса** — модель экспортирована в **ONNX**, в проде используется `onnxruntime` без sklearn.

### 3. UI — 11 + 5 (звёздочки)
- ✅ **[3] 3+ эндпоинта** — UI использует `/health`, `/users`, `/users/{id}/sessions`, `/users/{id}/sessions/{sid}/messages`, `/chat`, `/chat/async`, `/tasks/{id}`, `/classify`.
- ✅ **[2] Слабая связность** — `ui/api_client.py` использует только httpx + REST. Никаких импортов из `app/`.
- ✅ **[3] UX асинхронности** — везде `st.spinner`, для async-чата прогресс-бар + polling до завершения.
- ✅ **[1] Изоляция в сети** — UI подключён только к `frontend_net`. К `backend_net` (Postgres/Redis) доступа нет.
- ✅ **[2] Обработка сбоев** — `safe_call()` ловит 503/timeout/connection error и показывает понятное сообщение.
- ✅ **(5*) Визуальная репрезентация** — два Plotly-графика (latency-line и intent-pie), вкладка Analytics.

### 4. Reverse Proxy — 4
- ✅ **[1] Единая точка входа** — наружу торчит только nginx:80.
- ✅ **[2] Маршрутизация** — `/api/*` → upstream `api_backend`, `/` → `ui:8501`, `/grafana/`, `/prometheus/`.
- ✅ **[1] Rate Limiting** — `limit_req_zone ... rate=5r/m` (`docker/nginx/nginx.conf`).

### 5. Работа с данными — 5
- ✅ **[3] ORM** — SQLAlchemy 2.0 async, никаких сырых SQL-строк в коде (только `text("SELECT 1")` в health-чеке).
- ✅ **[2] Версионирование** — Alembic; миграция `0001_initial.py` создаёт все таблицы.

### 6. Docker Compose — 7 + 2 (звёздочки)
- ✅ **[2] Оптимизация сборок** — multi-stage Dockerfile.api / Dockerfile.worker / Dockerfile.ui.
- ✅ **(1*) Кэширование слоёв** — сначала `pyproject.toml`, потом `RUN uv pip install`, и только после — `COPY app`.
- ✅ **(1*) uv менеджмент** — все образы ставят зависимости через `uv pip install --system`.
- ✅ **[1] Разделение сетей** — `frontend_net`, `backend_net`, `monitoring_net`.
- ✅ **[2] Volumes** — `postgres_data`, `redis_data`, `model_weights`, `prometheus_data`, `grafana_data`.
- ✅ **[2] depends_on** — все сервисы зависят через `condition: service_healthy` или `service_completed_successfully`.

### 7. High Availability — 5 + 4 (звёздочки)
- ✅ **[3] Stateless** — состояние задач в БД (`tasks`-таблица) и Redis. API-инстансы взаимозаменяемы.
- ✅ **(2*) Горизонтальное масштабирование** — две реплики API (`api_a`, `api_b`) + `worker` с `replicas: 2`.
- ✅ **(2*) Балансировка** — Nginx `upstream { least_conn; api_a; api_b; }`.
- ✅ **[2] Graceful Shutdown** — `STOPSIGNAL SIGTERM`, `--timeout-graceful-shutdown 20` для uvicorn, `worker_shutdown_timeout=30` для Celery, `stop_grace_period` в compose.

### 8. Health & Monitoring — 6 + 3 (звёздочки)
- ✅ **[2] /health** проверяет БД, Redis, LLM (`app/api/health.py`).
- ✅ **[2] Compose healthcheck** — у postgres, redis, api_a, api_b, ui, nginx.
- ✅ **[2] depends_on: service_healthy** — везде, где это критично.
- ✅ **(3*) Метрики** — `prometheus-fastapi-instrumentator` экспортит `/metrics`; Prometheus + Grafana с готовым дашбордом.

**Итог обязательных:** 6 + 6 + 11 + 4 + 5 + 7 + 5 + 6 = **50 / 50**
**Со звёздочками:** **+22 балла** = **~72 / 75**

---

## 🧹 Управление контейнерами

```bash
docker compose up --build -d         # запустить всё
docker compose ps                    # статус
docker compose logs -f api_a         # логи одной реплики
docker compose logs -f worker        # логи воркера
docker compose down                  # остановить
docker compose down -v               # ОСТОРОЖНО: удалит и volumes (БД)
```

### Миграции вручную

```bash
docker compose exec api_a alembic revision --autogenerate -m "your message"
docker compose exec api_a alembic upgrade head
docker compose exec api_a alembic downgrade -1
```

### Тренировка локальной ONNX-модели

```bash
docker compose exec api_a python scripts/train_local_model.py
docker compose restart api_a api_b
# После чего эндпоинт /api/classify станет рабочим
```

---

## 📝 Заметки

- В `.env.example` нет реальных секретов — это безопасно для публикации в репо.
- Файл `.env` (с реальным `LLM_API_KEY`) **в репо не попадает** благодаря `.gitignore`.
- Веса моделей (`*.onnx`, `*.bin`, `*.gguf`) **не попадают в репо** — они генерируются при первом запуске и хранятся в volume `model_weights`.
- Prometheus и Grafana доступны через nginx (`/prometheus/`, `/grafana/`) — в проде закрой их HTTP-аутентификацией или vpn.
