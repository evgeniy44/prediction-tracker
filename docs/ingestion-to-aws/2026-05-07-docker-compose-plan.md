# Docker Compose Local Dev Implementation Plan (Task 17)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `docker-compose.yml` для local dev — один Postgres+pgvector service. Update `.env.example` з POSTGRES_* defaults. Update README.md з "Local development" workflow секцією.

**Architecture:** Single-service Compose: `postgres` (image `pgvector/pgvector:pg16`) на port 5432:5432, named volume `pgdata`, healthcheck via `pg_isready`. App + alembic migrations залишаються на host. No Dockerfile, no app container.

**Tech Stack:** Docker Compose v2, PostgreSQL 16 + pgvector extension, existing `alembic.ini` (host-based, конфігурує `localhost:5432`).

**Spec:** [`2026-05-07-docker-compose-design.md`](2026-05-07-docker-compose-design.md)

**Test count delta:** 0 (infrastructure config — manual smoke testing only).

---

## File Structure (locked-in)

```
prediction-tracker/
  docker-compose.yml       NEW (~25 lines)
  .env.example             MODIFIED — add POSTGRES_* section at end
  .env                     existing — operator updates manually (gitignored)
  README.md                MODIFIED — add "Local development" section before "Status"
  alembic.ini              UNCHANGED — sqlalchemy.url already matches Postgres credentials
```

---

## Task 1: Create `docker-compose.yml` + update `.env.example`

**Files:**
- Create: `docker-compose.yml`
- Modify: `.env.example` (append POSTGRES_* section)

### Step 1: Verify Docker Compose available

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
docker compose version
```

Expected: prints version (e.g., `Docker Compose version v2.x`). Якщо команда `docker compose` не знайдена — STATUS=BLOCKED, потрібен Docker Desktop або `docker-compose-plugin`.

### Step 2: Verify `docker-compose.yml` does not exist yet

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
ls docker-compose.yml 2>&1
```

Expected: `ls: cannot access ...` (file absent). Якщо існує — STATUS=BLOCKED, escalate.

### Step 3: Create `docker-compose.yml`

Create file `docker-compose.yml` at repo root with this exact content:

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

### Step 4: Verify YAML syntax

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
docker compose config 2>&1 | head -30
```

Expected: prints normalized service config (no syntax error). Якщо error — read it, виправ syntax, retry.

### Step 5: Update `.env.example` — add POSTGRES_* section

Read current `.env.example`. At the END of file, append:

```

# -- Docker Compose --
POSTGRES_USER=prophet
POSTGRES_PASSWORD=prophet
POSTGRES_DB=prophet_checker
```

Note the leading blank line — separates from preceding TG_SESSION_PATH section.

### Step 6: Verify `.env.example` content

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
tail -5 .env.example
```

Expected output:
```
# -- Docker Compose --
POSTGRES_USER=prophet
POSTGRES_PASSWORD=prophet
POSTGRES_DB=prophet_checker
```

### Step 7: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add docker-compose.yml .env.example
git commit -m "feat(infra): docker-compose.yml з postgres+pgvector для local dev (Task 17)"
```

---

## Task 2: Update `README.md` з "Local development" section

**Files:**
- Modify: `README.md` (insert section before "## Status")

### Step 1: Read current `README.md`

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
cat README.md
```

Note: section `## Status` should be at line ~19. We're inserting NEW section "## Local development" right BEFORE it.

### Step 2: Edit `README.md` — insert "Local development" section

In `README.md`, find:

```markdown
- Docker, AWS (EC2 + RDS)

## Status

Under development
```

Replace with:

```markdown
- Docker, AWS (EC2 + RDS)

## Local development

### Prereqs
- Docker Desktop (or compatible runtime) running
- `.venv` created via `pip install -e ".[dev]"`
- `.env` filled (use `.env.example` as template)

### Start
```bash
# 1. Bring up Postgres + pgvector
docker compose up -d
docker logs prophet_postgres   # check "ready to accept connections"

# 2. Apply migrations
.venv/bin/alembic upgrade head

# 3. Start FastAPI
.venv/bin/python -m prophet_checker
```

### Reset DB
```bash
docker compose down -v          # -v drops the pgdata volume
docker compose up -d
.venv/bin/alembic upgrade head
```

### Stop
```bash
docker compose down             # data preserved in pgdata volume
```

## Status

Under development
```

### Step 3: Verify the section was inserted correctly

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
grep -n "## " README.md
```

Expected output (порядок секцій):
```
4:## What it does
12:## Tech Stack
19:## Local development
...
?:## Status
?:## License
```

`Local development` має бути ПЕРЕД `Status`.

### Step 4: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add README.md
git commit -m "docs(readme): додаю секцію Local development з docker-compose workflow (Task 17)"
```

---

## Task 3: Manual smoke verification

This task creates **no commits** — only verifies the setup works end-to-end.

### Step 1: Bring up Postgres

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
docker compose up -d
```

Expected (first run downloads image; subsequent runs are fast):
```
[+] Running 2/2
 ✔ Network prediction-tracker_default      Created
 ✔ Container prophet_postgres              Started
```

### Step 2: Wait for healthy state

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
docker compose ps
```

Expected: row для `prophet_postgres` з STATUS `Up X seconds (healthy)`. Якщо `(starting)` — почекай 5-10 секунд і перевір знову. Якщо `(unhealthy)` — read `docker logs prophet_postgres`.

### Step 3: Verify pgvector extension available

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
docker exec prophet_postgres psql -U prophet -d prophet_checker -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
```

Expected: row показує `vector | 0.X.X` (де X.X — installed version). Якщо empty — image не має pgvector pre-installed (wrong tag).

### Step 4: Apply migrations from host

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> 89013292ec6d, add last_collected_at to person_sources`. (Або просто silent якщо вже applied.)

### Step 5: Verify schema applied

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/alembic current
```

Expected: `89013292ec6d (head)`.

### Step 6: Verify person_sources table з last_collected_at column

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
docker exec prophet_postgres psql -U prophet -d prophet_checker -c "\d person_sources"
```

Expected: показує table schema з колонкою `last_collected_at` (тип `timestamp with time zone`, NOT NULL).

### Step 7: Verify FastAPI app can boot

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -c "
import asyncio
from contextlib import AsyncExitStack
from prophet_checker.config import Settings
from prophet_checker.factory import build_orchestrator

async def main():
    settings = Settings()
    print('database_url:', settings.database_url)

asyncio.run(main())
"
```

Expected: prints `database_url: postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker`. Не запускаємо повний `python -m prophet_checker` бо потребує Telegram auth — але facto bootstrap config validates.

**(Optional, full smoke):** якщо `.env` має валідні Telegram credentials і session file існує — запусти `.venv/bin/python -m prophet_checker` у одному терміналі, в іншому `curl http://127.0.0.1:8000/health`. Has return `{"status":"ok"}`.

### Step 8: Cleanup

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
docker compose down
```

Expected: `Container prophet_postgres  Removed`. Volume `pgdata` зберігається.

For **reset to fresh state**: `docker compose down -v` (drops volume).

---

## Final verification

### Step 1: Verify all 3 deliverables landed

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
ls docker-compose.yml && grep "POSTGRES_" .env.example && grep "## Local development" README.md
```

Expected (all three lines visible):
```
docker-compose.yml
POSTGRES_USER=prophet
POSTGRES_PASSWORD=prophet
POSTGRES_DB=prophet_checker
## Local development
```

### Step 2: Verify git log

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git log --oneline -3
```

Expected (newest first):
```
<sha2> docs(readme): додаю секцію Local development з docker-compose workflow (Task 17)
<sha1> feat(infra): docker-compose.yml з postgres+pgvector для local dev (Task 17)
4bb638d docs: design spec — Docker Compose for local dev (Task 17)
```

### Step 3: Verify existing test suite still passes

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/ -q
```

Expected: `122 passed in X.Xs`. Жодних регресій (Task 17 не торкався Python коду).

---

## Out of Scope (deferred)

- ❌ Dockerfile для FastAPI app — AWS deploy task
- ❌ App service in compose — app на host
- ❌ Migration container service — manual з host
- ❌ Production overlay (`docker-compose.prod.yml`) — окремий AWS task
- ❌ Healthcheck-based startup ordering з app service — потрібен лише коли app у container
- ❌ Multi-architecture build для custom images — `pgvector/pgvector:pg16` already multi-arch
- ❌ Telethon session container mount — session на host
- ❌ Logs aggregation, secrets manager — поза scope
- ❌ Automated tests — infrastructure config tested manually

---

## Cross-references

- **Spec:** [`2026-05-07-docker-compose-design.md`](2026-05-07-docker-compose-design.md)
- **Task 16 FastAPI:** [`2026-05-05-fastapi-http-trigger-design.md`](2026-05-05-fastapi-http-trigger-design.md)
- **Architecture overview:** [`../architecture/2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md)
