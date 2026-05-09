# Prediction Tracker

AI-powered analysis and verification of predictions made by Ukrainian public figures.

## What it does

- Collects public statements from Telegram channels and news sites
- Extracts specific predictions using LLM
- Verifies predictions against real events with confidence scoring
- Provides interactive Telegram bot for querying results (RAG)

## Tech Stack

- Python 3.11+, FastAPI, SQLAlchemy 2.0
- PostgreSQL + pgvector (vector search)
- LiteLLM (provider-agnostic LLM abstraction)
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

### Integration smoke (real services)

Manual smoke script validates real Postgres + Telegram + Gemini + OpenAI integration end-to-end. Hits real APIs (~$0.001-0.005 per run depending on `--limit`).

**Prereqs (in addition to Local development setup):**
- `.env` filled з real API keys: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `LLM_API_KEY`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
- Telethon `tg_session` file existing (run `python -m prophet_checker` once interactively to auth)
- `docker compose up -d` running, `alembic upgrade head` applied

**Usage:**
```bash
# Cheap diagnostic — single component, often $0
.venv/bin/python scripts/integration_smoke.py --channel @arestovich --limit 1 --component postgres
.venv/bin/python scripts/integration_smoke.py --channel @arestovich --limit 1 --component gemini

# Full smoke — all 5 stages sequentially (~$0.001-0.005)
.venv/bin/python scripts/integration_smoke.py --channel @arestovich --limit 1

# Bulk-load full channel history
.venv/bin/python scripts/integration_smoke.py --channel @arestovich --limit 99999

# Reset smoke data + rerun
.venv/bin/python scripts/integration_smoke.py --channel @arestovich --limit 1 --reset-db

# Don't halt on first fail — collect all errors
.venv/bin/python scripts/integration_smoke.py --channel @arestovich --limit 1 --keep-going
```

**Stages:** `postgres` → `telegram` → `gemini` → `openai` → `e2e`. Use `--component STAGE` to run one stage in isolation.

Output: each stage prints `[N/5] stage ... ✓/✗ (Xs)  msg`. Exit code 0 on full pass, 1 on any fail.

## Tests

Unit + integration tests use in-memory fakes (`FakeSourceRepo`, `FakePredictionRepo`) — no Docker / network required.

```bash
# Full suite
.venv/bin/python -m pytest tests/ -q

# Specific file
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py -v

# Single test
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_run_cycle_no_active_sources -v

# With coverage
.venv/bin/python -m pytest tests/ --cov=prophet_checker --cov-report=term-missing
```

For real-services validation (Postgres + Telegram + LLM APIs) see "Integration smoke" section above.

## Status

Under development

## License

MIT
