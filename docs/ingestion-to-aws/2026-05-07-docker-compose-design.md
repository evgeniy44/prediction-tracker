# Docker Compose for Local Dev — Design Spec (Task 17)

**Status:** approved 2026-05-07
**Task:** 17 (master plan) — Local dev environment з Postgres + pgvector у Docker
**Prerequisites:** ✅ Task 15 (IngestionOrchestrator), ✅ Task 16 (FastAPI), ✅ Alembic migration
**Next:** Task 18-19 (real Postgres integration smoke з Telegram + Gemini), AWS deploy task окремо

---

## TL;DR

Один `docker-compose.yml` з ОДНИМ service — `postgres` (image `pgvector/pgvector:pg16`) для local dev. App залишається на host, запускається `python -m prophet_checker` напряму через `.venv`. Migrations теж runs з host через `.venv/bin/alembic upgrade head`.

Цей setup — infrastructure-блокер для Task 19 (integration smoke з real DB). FastAPI containerization — окремий task пізніше (AWS deploy track), не зараз.

---

## Architectural Decisions (Q1–Q3)

| # | Decision | Rationale |
|---|----------|-----------|
| Q1 | **Local-dev only; AWS production setup — окремий task** | Pet-project pragmatism + YAGNI. AWS deployment потребує окремого брейнштормингу (secrets, ECR, IAM, scheduled triggers). |
| Q2 | **Postgres у Docker, app на host** | Task 17 ціль = розблокувати real-DB testing для Task 19. Containerization app = scope creep — Dockerfile якісно писатиметься з real ECS context (multi-stage, healthcheck для ALB, IAM-based secrets), все що зараз — untested. |
| Q3 | **Manual `alembic upgrade head` з host** | `alembic.ini` вже сконфігурований для localhost:5432. Migration `compose service` додає image-build complexity без реальної цінності. AWS task додасть init-container pattern coли app буде containerized. |

---

## Components

### `docker-compose.yml` (NEW)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: prophet_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-prophet}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-prophet}
      POSTGRES_DB: ${POSTGRES_DB:-prophet_checker}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-prophet} -d ${POSTGRES_DB:-prophet_checker}"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

**Component decisions:**

| Аспект | Вибір | Alternative | Rationale |
|--------|-------|-------------|-----------|
| Image | `pgvector/pgvector:pg16` | `ankane/pgvector` | Офіційний образ pgvector проекту, активно maintained, pgvector pre-installed (no `CREATE EXTENSION` runtime магії) |
| Postgres version | 16 | 17 (latest) | LTS, supported until 2028, stable, всі major libraries compatible |
| Tag pinning | floating `:pg16` | `:0.8.0-pg16` (hard pin) | Pet project — простіше; trade-off у reproducibility прийнятний для local dev |
| Volume | named `pgdata` | bind mount `./data/postgres` | Docker-managed, чистіше для cleanup (`docker-compose down -v`); bind mount може мати permissions issues на macOS/Linux mix |
| Port | `5432:5432` exposed | random/none | host-side `alembic` + app потребують доступ |
| Container name | `prophet_postgres` | auto-generated | Зручно для `docker logs prophet_postgres` |
| Credentials | `prophet:prophet/prophet_checker` (default) | stronger password | Pet project, 127.0.0.1-only Docker exposure, no public surface |
| Healthcheck | `pg_isready` 5s interval | none | Useful для `docker-compose ps` debug + майбутній `depends_on: condition: service_healthy` |

### `.env.example` additions

```bash
# -- Docker Compose --
POSTGRES_USER=prophet
POSTGRES_PASSWORD=prophet
POSTGRES_DB=prophet_checker
```

`.env` (gitignored) — ті самі рядки. Defaults у compose означають що відсутність змінних не зламає setup — usability bonus.

### `alembic.ini` reconciliation

**No changes.** Поточний `sqlalchemy.url = postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker` (line 3) уже узгоджений з нашими credentials defaults.

### `README.md` updates (NEW section)

Додаємо секцію "Local development" перед "Status":

```markdown
## Local development

### Prereqs
- Docker Desktop (or compatible runtime) running
- `.venv` created via `pip install -e ".[dev]"`
- `.env` filled (use `.env.example` as template)

### Start
```bash
# 1. Bring up Postgres + pgvector
docker-compose up -d
docker logs prophet_postgres   # check "ready to accept connections"

# 2. Apply migrations
.venv/bin/alembic upgrade head

# 3. Start FastAPI
.venv/bin/python -m prophet_checker
```

### Reset DB
```bash
docker-compose down -v          # -v drops the pgdata volume
docker-compose up -d
.venv/bin/alembic upgrade head
```

### Stop
```bash
docker-compose down             # data preserved in pgdata volume
```
```

---

## Workflow

```mermaid
sequenceDiagram
    actor Dev
    participant Compose as docker-compose
    participant Pg as postgres container<br/>(pgvector/pgvector:pg16)
    participant Volume as pgdata volume
    participant Alembic as alembic (host)
    participant App as python -m prophet_checker

    Dev->>Compose: docker-compose up -d
    Compose->>Pg: pull image, start container
    Pg->>Volume: mount /var/lib/postgresql/data
    Pg->>Pg: healthcheck loop (pg_isready)
    Note over Pg: ready to accept connections

    Dev->>Alembic: .venv/bin/alembic upgrade head
    Alembic->>Pg: connect localhost:5432
    Alembic->>Pg: read alembic_version → empty
    Alembic->>Pg: apply 89013292ec6d (last_collected_at)
    Alembic->>Pg: insert alembic_version row
    Note over Pg: schema ready

    Dev->>App: .venv/bin/python -m prophet_checker
    App->>Pg: connect via factory.build_orchestrator
    Note over App: serving on 127.0.0.1:8000

    Dev->>Compose: docker-compose down (later)
    Compose->>Pg: stop container
    Note over Volume: pgdata persists
```

---

## Out of Scope (explicitly deferred)

- ❌ **App container (FastAPI Dockerfile)** — AWS deploy task; зараз app на host для fast iteration
- ❌ **Migration container service** — manual з host достатньо; init-container pattern для AWS
- ❌ **Production compose overlay** (`docker-compose.prod.yml`) — окремий AWS task
- ❌ **Multi-architecture image** (linux/amd64 + linux/arm64) — `pgvector/pgvector:pg16` already multi-arch
- ❌ **Telethon session container mount** — session file у repo root, app на host читає напряму
- ❌ **Logs aggregation** (Loki, CloudWatch, etc.) — `docker logs prophet_postgres` достатньо
- ❌ **Secrets manager integration** (AWS SSM, Vault) — `.env` for local dev
- ❌ **Healthcheck-based startup ordering** (`depends_on: condition: service_healthy`) — потрібно лише коли app у container; зараз app stops на host manually
- ❌ **Volume backup strategy** — `docker-compose down -v` для reset, нема production data

---

## Testing

**No automated tests** — це infrastructure config. Manual smoke:

```bash
# Bring up
docker-compose up -d

# Verify postgres ready
docker-compose ps              # postgres "running (healthy)"

# Verify pgvector extension available
docker exec prophet_postgres psql -U prophet -d prophet_checker \
    -c "SELECT extname FROM pg_extension WHERE extname='vector';"
# Expected: vector

# Verify alembic + schema
.venv/bin/alembic upgrade head
.venv/bin/alembic current      # 89013292ec6d (head)

# Verify app starts cleanly
.venv/bin/python -m prophet_checker  # should bootstrap orchestrator without errors
                                     # Ctrl+C to stop

# Cleanup
docker-compose down
```

Automated integration smoke з real Postgres — **Task 19 scope**.

---

## Cross-references

- **Task 16 FastAPI:** [`2026-05-05-fastapi-http-trigger-design.md`](2026-05-05-fastapi-http-trigger-design.md)
- **Task 15 IngestionOrchestrator:** [`2026-05-01-ingestion-orchestrator-design.md`](2026-05-01-ingestion-orchestrator-design.md)
- **LLM Client Split:** [`2026-05-01-llm-client-split-design.md`](2026-05-01-llm-client-split-design.md)
- **Architecture overview:** [`../architecture/2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md)
