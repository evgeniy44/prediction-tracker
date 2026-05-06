# FastAPI HTTP-Trigger Implementation Plan (Task 16)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a thin FastAPI HTTP-wrapper around `IngestionOrchestrator.run_cycle()` exposing `POST /ingest/run` (sync) and `GET /health`. Manual MVP — no auth, no concurrency lock.

**Architecture:** Three flat files: `factory.py` (wiring DB engine, Telegram client, repos, orchestrator with `AsyncExitStack` resource registration), `app.py` (FastAPI app with lifespan-based factory invocation), `__main__.py` (uvicorn entry). Defensive endpoint: 503 if `app.state.orchestrator` missing, 500 on catastrophic exception, 200 with per-channel errors otherwise.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, SQLAlchemy 2.0 async, Telethon, pydantic-settings, httpx (test client), pytest-asyncio.

**Spec:** [`2026-05-05-fastapi-http-trigger-design.md`](2026-05-05-fastapi-http-trigger-design.md)

**Test count delta:** +8 (5 endpoint + 2 factory + 1 config). 114 → 122.

---

## File Structure (locked-in)

```
src/prophet_checker/
  config.py        MODIFIED: add openai_api_key + tg_session_path fields
  factory.py       NEW: build_orchestrator(settings, stack) — wiring без HTTP
  app.py           NEW: FastAPI app + lifespan + endpoints
  __main__.py      NEW: uvicorn entry point

.env.example       MODIFIED: add TG_SESSION_PATH note (OPENAI_API_KEY already present)

tests/
  test_config.py            MODIFIED: 1 нова assertion на нові поля
  test_factory.py           NEW (2 tests)
  test_app_endpoints.py     NEW (5 tests)

tests/conftest.py           MODIFIED: extend env_vars fixture з OPENAI_API_KEY + TG_SESSION_PATH
```

---

## Task 1: Settings — add `openai_api_key` + `tg_session_path` fields

**Files:**
- Modify: `src/prophet_checker/config.py:4-19` (Settings class)
- Modify: `tests/conftest.py:4-12` (env_vars fixture)
- Modify: `tests/test_config.py:4-21` (existing tests + 1 нова)
- Modify: `.env.example` (add TG_SESSION_PATH)

### Step 1: Read current `tests/test_config.py` to confirm baseline

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_config.py -v
```

Expected: 2 tests pass.

### Step 2: Append failing test to `tests/test_config.py`

```python
def test_settings_includes_fastapi_fields(env_vars):
    settings = Settings()
    assert settings.openai_api_key == "sk-test-openai-key"
    assert settings.tg_session_path == "/tmp/test_session"
```

### Step 3: Run new test, expect failure

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_config.py::test_settings_includes_fastapi_fields -v
```

Expected: FAIL — `Settings` не має полів `openai_api_key` і `tg_session_path`.

### Step 4: Update `Settings` class

In `src/prophet_checker/config.py`, find:

```python
class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    embedding_model: str = "text-embedding-3-small"
    verification_confidence_threshold: float = 0.6
```

Replace with:

```python
class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: str = ""
    tg_session_path: str = "tg_session"
    verification_confidence_threshold: float = 0.6
```

### Step 5: Update `tests/conftest.py` env_vars fixture

In `tests/conftest.py`, find:

```python
@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "test-hash")
```

Replace with:

```python
@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "test-hash")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key")
    monkeypatch.setenv("TG_SESSION_PATH", "/tmp/test_session")
```

### Step 6: Update `.env.example`

In `.env.example`, find:

```
# -- Telegram (data collection) --
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_API_ID=your-api-id
TELEGRAM_API_HASH=your-api-hash
```

Replace with:

```
# -- Telegram (data collection) --
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_API_ID=your-api-id
TELEGRAM_API_HASH=your-api-hash
TG_SESSION_PATH=tg_session
```

### Step 7: Run new test, verify pass

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_config.py -v
```

Expected: 3 tests pass.

### Step 8: Run full suite

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/ -q
```

Expected: 115 passing (114 baseline + 1 new test).

### Step 9: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/config.py tests/conftest.py tests/test_config.py .env.example
git commit -m "feat(config): додаю openai_api_key + tg_session_path для Task 16 FastAPI"
```

---

## Task 2: factory.py — `build_orchestrator(settings, stack)`

**Files:**
- Create: `src/prophet_checker/factory.py`
- Create: `tests/test_factory.py`

### Step 1: Create `tests/test_factory.py` skeleton + first test

```python
from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prophet_checker.config import Settings
from prophet_checker.factory import build_orchestrator
from prophet_checker.ingestion import IngestionOrchestrator


def _settings_with_test_env(monkeypatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test")
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "test-hash")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.setenv("TG_SESSION_PATH", "/tmp/test_session")
    return Settings()


async def test_build_orchestrator_returns_orchestrator(monkeypatch):
    settings = _settings_with_test_env(monkeypatch)

    with patch("prophet_checker.factory.TelegramClient") as MockTg:
        mock_tg_instance = MockTg.return_value
        mock_tg_instance.start = AsyncMock()
        mock_tg_instance.disconnect = AsyncMock()

        async with AsyncExitStack() as stack:
            orchestrator = await build_orchestrator(settings, stack)
            assert isinstance(orchestrator, IngestionOrchestrator)
```

### Step 2: Run, expect ImportError

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_factory.py::test_build_orchestrator_returns_orchestrator -v
```

Expected: ImportError on `prophet_checker.factory`.

### Step 3: Create `src/prophet_checker/factory.py`

```python
from __future__ import annotations

from contextlib import AsyncExitStack

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from telethon import TelegramClient

from prophet_checker.analysis.extractor import PredictionExtractor
from prophet_checker.config import Settings
from prophet_checker.ingestion import IngestionOrchestrator
from prophet_checker.llm import EmbeddingClient, LLMClient
from prophet_checker.models.domain import SourceType
from prophet_checker.sources.telegram import TelegramSource
from prophet_checker.storage.postgres import (
    PostgresPredictionRepository,
    PostgresSourceRepository,
)


async def build_orchestrator(
    settings: Settings, stack: AsyncExitStack
) -> IngestionOrchestrator:
    engine = create_async_engine(settings.database_url, echo=False)
    stack.push_async_callback(engine.dispose)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    source_repo = PostgresSourceRepository(session_factory)
    prediction_repo = PostgresPredictionRepository(session_factory)

    llm = LLMClient(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
    )
    embedder = EmbeddingClient(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )
    extractor = PredictionExtractor(llm)

    tg_client = TelegramClient(
        session=settings.tg_session_path,
        api_id=settings.telegram_api_id,
        api_hash=settings.telegram_api_hash,
    )
    await tg_client.start()
    stack.push_async_callback(tg_client.disconnect)
    telegram_source = TelegramSource(tg_client)

    return IngestionOrchestrator(
        session_factory=session_factory,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: telegram_source},
    )
```

### Step 4: Run test, verify pass

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_factory.py::test_build_orchestrator_returns_orchestrator -v
```

Expected: PASS.

### Step 5: Append cleanup-registration test to `tests/test_factory.py`

```python
async def test_build_orchestrator_registers_cleanup(monkeypatch):
    settings = _settings_with_test_env(monkeypatch)

    with patch("prophet_checker.factory.TelegramClient") as MockTg:
        mock_tg_instance = MockTg.return_value
        mock_tg_instance.start = AsyncMock()
        mock_tg_instance.disconnect = AsyncMock()

        async with AsyncExitStack() as stack:
            await build_orchestrator(settings, stack)

        mock_tg_instance.disconnect.assert_called_once()
```

### Step 6: Run, verify pass

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_factory.py -v
```

Expected: 2 tests pass.

### Step 7: Run full suite

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/ -q
```

Expected: 117 passing (115 + 2 new factory tests).

### Step 8: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/factory.py tests/test_factory.py
git commit -m "feat(factory): build_orchestrator wiring з AsyncExitStack cleanup (Task 16)"
```

---

## Task 3: app.py — FastAPI app + lifespan + endpoints

**Files:**
- Create: `src/prophet_checker/app.py`
- Create: `tests/test_app_endpoints.py`

This task is the largest — 5 endpoint tests. Subdivide into TDD slices.

### Slice 3a: Health endpoint

#### Step 1: Create `tests/test_app_endpoints.py` skeleton + first test

```python
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from prophet_checker.app import app
from prophet_checker.ingestion import ChannelReport, CycleReport


async def test_health_returns_ok():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

#### Step 2: Run, expect ImportError

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_app_endpoints.py::test_health_returns_ok -v
```

Expected: ImportError on `prophet_checker.app`.

#### Step 3: Create minimal `src/prophet_checker/app.py`

```python
from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from prophet_checker.config import Settings
from prophet_checker.factory import build_orchestrator
from prophet_checker.ingestion import CycleReport

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    async with AsyncExitStack() as stack:
        orchestrator = await build_orchestrator(settings, stack)
        app.state.orchestrator = orchestrator
        yield


app = FastAPI(title="prediction-tracker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

#### Step 4: Run health test, verify pass

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_app_endpoints.py::test_health_returns_ok -v
```

Expected: PASS. (Note: lifespan не запускається у test client without explicit context — health endpoint не потребує `app.state.orchestrator`, тож test проходить.)

#### Step 5: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/app.py tests/test_app_endpoints.py
git commit -m "feat(app): FastAPI skeleton + GET /health endpoint (Task 16 slice 3a)"
```

---

### Slice 3b: POST /ingest/run — happy path

#### Step 1: Append test

```python
async def test_ingest_run_returns_cycle_report():
    orchestrator = MagicMock()
    orchestrator.run_cycle = AsyncMock(return_value=CycleReport(
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        channels_processed=[
            ChannelReport(
                person_source_id="ps1",
                posts_seen=3,
                posts_with_predictions=2,
                predictions_extracted=5,
            ),
        ],
    ))
    app.state.orchestrator = orchestrator

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ingest/run")

    assert resp.status_code == 200
    body = resp.json()
    assert "channels_processed" in body
    assert "started_at" in body
    assert "finished_at" in body
    assert len(body["channels_processed"]) == 1
    assert body["channels_processed"][0]["person_source_id"] == "ps1"
    assert body["channels_processed"][0]["predictions_extracted"] == 5
```

#### Step 2: Run, expect 404 or AttributeError

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_app_endpoints.py::test_ingest_run_returns_cycle_report -v
```

Expected: FAIL — endpoint `/ingest/run` ще не існує.

#### Step 3: Add `POST /ingest/run` endpoint to `src/prophet_checker/app.py`

After the `health()` function, append:

```python
@app.post("/ingest/run", response_model=CycleReport)
async def run_ingestion(request: Request) -> CycleReport:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="orchestrator not initialized — server is starting up or shutting down",
        )
    try:
        return await orchestrator.run_cycle()
    except Exception as exc:
        logger.exception("run_cycle failed catastrophically")
        raise HTTPException(
            status_code=500,
            detail=f"unexpected orchestrator failure: {type(exc).__name__}",
        )
```

#### Step 4: Run test, verify pass

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_app_endpoints.py -v
```

Expected: 2 tests pass.

#### Step 5: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/app.py tests/test_app_endpoints.py
git commit -m "feat(app): POST /ingest/run з 503/500 error handling (Task 16 slice 3b)"
```

---

### Slice 3c: 503 when orchestrator not initialized

#### Step 1: Append test

```python
async def test_ingest_run_503_when_orchestrator_not_initialized():
    if hasattr(app.state, "orchestrator"):
        delattr(app.state, "orchestrator")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ingest/run")

    assert resp.status_code == 503
    assert "orchestrator not initialized" in resp.json()["detail"]
```

#### Step 2: Run, verify pass (logic вже implemented in slice 3b)

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_app_endpoints.py::test_ingest_run_503_when_orchestrator_not_initialized -v
```

Expected: PASS.

#### Step 3: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add tests/test_app_endpoints.py
git commit -m "test(app): 503 коли orchestrator не ініціалізований (Task 16 slice 3c)"
```

---

### Slice 3d: 500 on catastrophic exception

#### Step 1: Append test

```python
async def test_ingest_run_500_on_catastrophic_exception():
    orchestrator = MagicMock()
    orchestrator.run_cycle = AsyncMock(side_effect=RuntimeError("boom"))
    app.state.orchestrator = orchestrator

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ingest/run")

    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "RuntimeError" in detail
    assert "boom" not in detail
```

(Sanitized detail — exception type ім'я тільки, не raw message. Це prevent'ить leakage of internal data.)

#### Step 2: Run, verify pass

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_app_endpoints.py::test_ingest_run_500_on_catastrophic_exception -v
```

Expected: PASS.

#### Step 3: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add tests/test_app_endpoints.py
git commit -m "test(app): 500 на catastrophic exception (Task 16 slice 3d)"
```

---

### Slice 3e: Per-channel errors return 200

#### Step 1: Append test

```python
async def test_ingest_run_returns_per_channel_errors_as_200():
    orchestrator = MagicMock()
    orchestrator.run_cycle = AsyncMock(return_value=CycleReport(
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        channels_processed=[
            ChannelReport(
                person_source_id="ps1",
                posts_seen=2,
                error="halted at step=processing: LLM 503",
            ),
            ChannelReport(
                person_source_id="ps2",
                posts_seen=5,
                predictions_extracted=3,
            ),
        ],
    ))
    app.state.orchestrator = orchestrator

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ingest/run")

    assert resp.status_code == 200
    body = resp.json()
    channels = body["channels_processed"]
    assert len(channels) == 2
    assert channels[0]["error"] is not None
    assert "halted" in channels[0]["error"]
    assert channels[1]["error"] is None
```

#### Step 2: Run, verify pass

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_app_endpoints.py::test_ingest_run_returns_per_channel_errors_as_200 -v
```

Expected: PASS.

#### Step 3: Run full app endpoint suite

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_app_endpoints.py -v
```

Expected: 5 tests pass.

#### Step 4: Run full suite

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/ -q
```

Expected: 122 passing (117 + 5 new endpoint tests).

#### Step 5: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add tests/test_app_endpoints.py
git commit -m "test(app): per-channel halt повертає 200 (Task 16 slice 3e)"
```

---

## Task 4: __main__.py — uvicorn entry point

**Files:**
- Create: `src/prophet_checker/__main__.py`

### Step 1: Create `src/prophet_checker/__main__.py`

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "prophet_checker.app:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
```

### Step 2: Verify import works

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -c "import prophet_checker.__main__; print('OK')"
```

Expected: `OK`.

### Step 3: Run full suite

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/ -q
```

Expected: 122 passing (no new tests, just new module).

### Step 4: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/__main__.py
git commit -m "feat(app): uvicorn entry point — python -m prophet_checker (Task 16)"
```

---

## Final verification

### Step 1: Run full test suite

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/ -v
```

Expected: 122 tests passing. Specifically:
- 114 baseline (after Task 15)
- +1 from `test_config.py` (Task 1)
- +2 from `test_factory.py` (Task 2)
- +5 from `test_app_endpoints.py` (Task 3)
- = **122 passing**

### Step 2: Verify module imports

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -c "
from prophet_checker.app import app
from prophet_checker.factory import build_orchestrator
from prophet_checker.config import Settings
print('OK:', app, build_orchestrator, Settings)
"
```

Expected: `OK: <fastapi.FastAPI ...> <function ...> <class ...>`.

### Step 3: Verify FastAPI app structure

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -c "
from prophet_checker.app import app
routes = [(r.path, sorted(r.methods)) for r in app.routes if hasattr(r, 'methods')]
expected = [('/health', ['GET']), ('/ingest/run', ['POST'])]
for exp in expected:
    assert exp in routes, f'{exp} missing'
print('OK: routes wired correctly')
"
```

Expected: `OK: routes wired correctly`.

### Step 4: Manual smoke test (optional, requires local Postgres + .env)

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m prophet_checker
```

In another terminal:

```bash
curl -i http://127.0.0.1:8000/health
```

Expected: `HTTP/1.1 200 OK` with `{"status":"ok"}`.

```bash
curl -i -X POST http://127.0.0.1:8000/ingest/run
```

Expected: `HTTP/1.1 200 OK` with `CycleReport` JSON. (Якщо Postgres не доступний — startup впаде з clear error message.)

`Ctrl+C` зупиняє server. Lifespan `__aexit__` тригерить teardown — disconnect Telegram + dispose engine.

**Note:** Manual smoke не обов'язковий для completion. Якщо real Postgres + Telegram session не налаштовані локально — це OK; Task 19 буде ловити такі проблеми.

---

## Out of Scope (deferred)

- ❌ Real lifespan-startup test з real Postgres + Telegram — Task 19
- ❌ Concurrent `/ingest/run` requests — no lock, manual MVP
- ❌ Auth middleware — Bearer token / IP allowlist when public deploy
- ❌ Async / job-id pattern (202 Accepted + GET /jobs/:id) — sync sufficient
- ❌ Admin endpoints (cursor reset, list-stuck-channels) — manual SQL works
- ❌ Metrics / Prometheus / OpenTelemetry — log-based monitoring sufficient

---

## Cross-references

- **Spec:** [`2026-05-05-fastapi-http-trigger-design.md`](2026-05-05-fastapi-http-trigger-design.md)
- **Task 15 IngestionOrchestrator:** [`2026-05-01-ingestion-orchestrator-design.md`](2026-05-01-ingestion-orchestrator-design.md)
- **LLM Client Split:** [`2026-05-01-llm-client-split-design.md`](2026-05-01-llm-client-split-design.md)
- **Architecture overview:** [`../architecture/2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md)
