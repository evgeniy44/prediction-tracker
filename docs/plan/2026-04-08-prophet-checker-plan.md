# Prophet Checker (prediction-tracker) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **MANDATORY GATE:** After completing each task, STOP and ask the user for explicit confirmation before proceeding to the next task. Show a summary of what was done (files created/modified, tests passed, commit hash) and wait for approval. Do NOT proceed to the next task without user saying "ok", "go", "next", or similar explicit confirmation. This applies to every single task — no exceptions.

**Goal:** Build a Telegram bot that analyzes and verifies predictions made by Ukrainian public figures, using LLM-powered extraction, verification, and RAG-based chat.

**Architecture:** Monolith FastAPI app with five modules (bot, analysis, sources, llm, storage). Storage abstracted behind Protocol interfaces with PostgreSQL+pgvector implementation. Pluggable source collectors. LLM provider abstraction via LiteLLM.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, pgvector, LiteLLM, aiogram, Docker, PostgreSQL, AWS (EC2 + RDS)

**Spec:** `docs/superpowers/specs/2026-04-07-prophet-checker-design.md`

**Repo:** `github.com/evgeniy44/prediction-tracker` (public)

**Pace:** Slow and deliberate. Each task is a separate session/day. No rushing — quality over speed.

**Todoist:** Project "Prediction Tracker" (ID: `6gJx4cR2fgJQgwHq`) — tasks with subtasks mirror this plan. Complete subtasks as you go.

---

## Project Status (updated 2026-04-21)

> This master plan is a **living document** — each task header shows current status. Completed tasks include retrospective notes (what was actually built, key deviations from original plan, commit refs). Detailed implementation specs for in-flight tasks live in separate files (e.g. Task 13.5).

### Status legend

| Symbol | Meaning |
|---|---|
| ✅ COMPLETE | Done, committed, validated |
| 🔄 IN PROGRESS | Currently being worked on |
| 📋 PLANNED | In scope, not started |
| ⏸ DEFERRED | Removed from active queue, may revisit |
| ❌ REMOVED | Cut from project scope |

### Milestones

| Milestone | Tasks | Status | Notes |
|---|---|---|---|
| **M1: Foundation** | 0-4 | ✅ COMPLETE | All 5 tasks shipped. Scaffold, domain models, storage interfaces, ORM + Alembic. |
| **M2: AI Pipeline** | 5-9 | ✅ COMPLETE | LLM client, prompts, PredictionExtractor, PredictionVerifier. 38 unit tests. |
| **M2.5: Eval & Data** | 10, 12-14 | 🔄 IN PROGRESS | Task 10 ✅, Task 12 ✅ (130 gold labels), Task 13 ✅ (Gemini wins F1=0.848), Task 13.5 📋 (extraction quality plan ready), Task 14 ⏸ deferred. *Task 11 ❌ removed 2026-04-20 — MVP trimmed to Telegram-only.* |
| **M3: Orchestration** | 15-16 | 📋 PLANNED | Ingestion pipeline orchestrator + FastAPI app entry point. |
| **M4: Database & Infra** | 17-19 | 📋 PLANNED | Docker Compose, Alembic migration, integration smoke. |
| **M5: CI & Sources** | 20-22 | 📋 PLANNED | GitHub Actions CI, Telegram Source adapter, news collector. |
| **M6: AWS Deploy** | 23-24 | 📋 PLANNED | RDS PostgreSQL + pgvector, EC2 deploy. |

### Active follow-up specs

- **Task 13.5 — Extraction Quality Eval** (📋 plan ready, not executed)
  - Spec: [`2026-04-21-extraction-quality-eval-design.md`](../extraction-quality-eval/2026-04-21-extraction-quality-eval-design.md) (commit `403f2fb`)
  - Plan: [`2026-04-21-extraction-quality-eval-plan.md`](../extraction-quality-eval/2026-04-21-extraction-quality-eval-plan.md) (commit `ee0b052`)

### Recent commits

```
7204b91 docs: retrospective rewrite of Task 13 in master plan
ee0b052 docs: implementation plan for extraction quality eval (Task 13.5)
403f2fb docs: design spec for extraction quality eval (Task 13.5)
774c340 docs: remove Task 11 (YouTube transcripts)
3da94a3 feat: detection evaluation harness + 5-model P/R/F1 results (Task 13)
3635eb0 [intermediate] production code fixes for Task 13 (parser, retries, config)
a992e0f feat: extend gold labels to 130 posts + refine edge case guidelines (Task 12)
428aea4 feat: add annotation guidelines and gold labels for 50 posts (Task 12 initial)
d7c9e5e feat: add Telegram post collection script (Task 10)
20746b8 feat: implement PredictionVerifier (Task 9)
610b0dd feat: implement PredictionExtractor (Task 8)
006a458 feat: add prompt templates for extraction, verification, and RAG (Task 7)
f90eb07 feat: add LLM client with LiteLLM abstraction (Task 6)
cd25af0 feat: add PostgreSQL storage implementation (Task 5)
1ca8a16 feat: add SQLAlchemy ORM models and Alembic config (Task 4)
035468e feat: add storage Protocol interfaces (Task 3)
04e195c feat: add Pydantic domain models (Task 2)
2f736de feat: project scaffold with config, dependencies, and tests (Task 1)
```

---

## Task 0: GitHub Repository Setup ✅ COMPLETE (commits 83fc1dc, 693995a — initial repo + planning)

**Files:**
- Create: GitHub repo `prediction-tracker`
- Create: `prediction-tracker/README.md`
- Create: `prediction-tracker/.gitignore`
- Create: `prediction-tracker/LICENSE`

- [ ] **Step 1: Install GitHub CLI (if not installed)**

```bash
brew install gh
```

If brew is not available:
```bash
curl -sS https://webi.sh/gh | sh
```

- [ ] **Step 2: Authenticate with GitHub**

```bash
gh auth login
```

Follow the interactive prompts (browser-based auth recommended).

- [ ] **Step 3: Create the repository**

```bash
gh repo create prediction-tracker --public --description "AI-powered analysis of public figures' predictions" --clone
cd prediction-tracker
```

- [ ] **Step 4: Create initial files**

```gitignore
# prediction-tracker/.gitignore
.venv/
__pycache__/
*.pyc
*.egg-info/
dist/
.ruff_cache/
.env
*.session
*.session-journal
.superpowers/
```

```markdown
# prediction-tracker/README.md
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

## Status

🚧 Under development

## License

MIT
```

```
# prediction-tracker/LICENSE
MIT License

Copyright (c) 2026 Yevhenii Berlog

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 5: Initial commit and push**

```bash
git add .
git commit -m "Initial commit: README, .gitignore, LICENSE"
git push -u origin main
```

**🏁 End of Task 0.** STOP. Show summary to user. Wait for explicit approval before Task 1.

---

## File Structure

```
prediction-tracker/
├── pyproject.toml                          # Project config, dependencies
├── Dockerfile                              # Multi-stage Docker build
├── docker-compose.yml                      # App + PostgreSQL for local dev
├── .env.example                            # Environment variables template
├── alembic.ini                             # Alembic config
├── alembic/
│   ├── env.py                              # Alembic environment (async)
│   └── versions/                           # Migration files
├── src/
│   └── prophet_checker/
│       ├── __init__.py
│       ├── main.py                         # FastAPI app entry, lifespan
│       ├── config.py                       # Pydantic settings
│       ├── models/
│       │   ├── __init__.py
│       │   ├── domain.py                   # Pydantic domain models
│       │   └── db.py                       # SQLAlchemy ORM models
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── interfaces.py               # Protocol interfaces
│       │   └── postgres.py                 # PostgreSQL implementation
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── client.py                   # LiteLLM wrapper
│       │   └── prompts.py                  # Prompt templates
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── interface.py                # Source protocol
│       │   ├── telegram_collector.py       # Telegram channel collector
│       │   └── news_collector.py           # News RSS/scraper
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── extractor.py                # Prediction extraction via LLM
│       │   └── verifier.py                 # Prediction verification via LLM
│       └── bot/
│           ├── __init__.py
│           └── handlers.py                 # Telegram bot handlers + RAG
├── tests/
│   ├── conftest.py                         # Shared fixtures
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_storage_interfaces.py
│   ├── test_storage_postgres.py
│   ├── test_llm_client.py
│   ├── test_llm_prompts.py
│   ├── test_sources_telegram.py
│   ├── test_sources_news.py
│   ├── test_analysis_extractor.py
│   ├── test_analysis_verifier.py
│   └── test_bot_handlers.py
```

---

## Task 1: Project Scaffold ✅ COMPLETE (commit 2f736de)

**Files:**
- Create: `prediction-tracker/pyproject.toml`
- Create: `prediction-tracker/src/prophet_checker/__init__.py`
- Create: `prediction-tracker/src/prophet_checker/config.py`
- Create: `prediction-tracker/tests/conftest.py`
- Create: `prediction-tracker/tests/test_config.py`
- Create: `prediction-tracker/.env.example`

- [ ] **Step 1: Create project directory and pyproject.toml**

```bash
mkdir -p prediction-tracker/src/prophet_checker prediction-tracker/tests
```

```toml
# prediction-tracker/pyproject.toml
[project]
name = "prophet-checker"
version = "0.1.0"
description = "AI-powered analysis of public figures' predictions"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "pgvector>=0.3.0",
    "alembic>=1.14.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "litellm>=1.50.0",
    "aiogram>=3.13.0",
    "httpx>=0.27.0",
    "feedparser>=6.0.0",
    "beautifulsoup4>=4.12.0",
    "telethon>=1.37.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.6.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
target-version = "py311"
line-length = 100

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

- [ ] **Step 2: Create .env.example**

```bash
# prediction-tracker/.env.example
DATABASE_URL=postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your-key-here
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_API_ID=your-api-id
TELEGRAM_API_HASH=your-api-hash
```

- [ ] **Step 3: Create config module**

```python
# prediction-tracker/src/prophet_checker/__init__.py
```

```python
# prediction-tracker/src/prophet_checker/config.py
from pydantic_settings import BaseSettings


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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write test for config**

```python
# prediction-tracker/tests/conftest.py
import pytest


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

```python
# prediction-tracker/tests/test_config.py
from prophet_checker.config import Settings


def test_settings_from_env(env_vars):
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://test:test@localhost:5432/test_db"
    assert settings.llm_provider == "openai"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.llm_api_key == "sk-test-key"
    assert settings.telegram_bot_token == "test-bot-token"


def test_settings_defaults():
    settings = Settings(
        llm_api_key="key",
        telegram_bot_token="token",
        telegram_api_id=1,
        telegram_api_hash="hash",
    )
    assert settings.database_url == "postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker"
    assert settings.verification_confidence_threshold == 0.6
```

- [ ] **Step 5: Install dependencies and run tests**

```bash
cd prediction-tracker
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_config.py -v
```

Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ tests/ .env.example
git commit -m "feat: project scaffold with config and dependencies"
git push
```

**🏁 End of Task 1.** STOP. Show summary to user. Wait for explicit approval before Task 2.

---

## Task 2: Domain Models ✅ COMPLETE (commit 04e195c)

**Files:**
- Create: `prediction-tracker/src/prophet_checker/models/__init__.py`
- Create: `prediction-tracker/src/prophet_checker/models/domain.py`
- Create: `prediction-tracker/tests/test_models.py`

- [ ] **Step 1: Write tests for domain models**

```python
# prediction-tracker/tests/test_models.py
from datetime import date, datetime
from prophet_checker.models.domain import (
    Person,
    PersonSource,
    RawDocument,
    Prediction,
    PredictionStatus,
    SourceType,
)


def test_person_creation():
    person = Person(id="1", name="Арестович", description="Політичний оглядач")
    assert person.name == "Арестович"
    assert person.description == "Політичний оглядач"


def test_person_source_creation():
    ps = PersonSource(
        id="1",
        person_id="1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovych",
        enabled=True,
    )
    assert ps.source_type == SourceType.TELEGRAM
    assert ps.source_identifier == "@arestovych"
    assert ps.enabled is True


def test_raw_document_creation():
    doc = RawDocument(
        id="1",
        person_id="1",
        source_type=SourceType.TELEGRAM,
        url="https://t.me/arestovych/1234",
        published_at=datetime(2023, 6, 15, 10, 30),
        raw_text="Контрнаступ почнеться влітку",
        language="uk",
        collected_at=datetime(2024, 1, 1, 12, 0),
    )
    assert doc.source_type == SourceType.TELEGRAM
    assert doc.language == "uk"


def test_prediction_creation():
    pred = Prediction(
        id="1",
        document_id="1",
        person_id="1",
        claim_text="Контрнаступ почнеться влітку 2023",
        prediction_date=date(2023, 1, 12),
        target_date=date(2023, 6, 1),
        topic="війна",
        status=PredictionStatus.UNRESOLVED,
        confidence=0.0,
    )
    assert pred.status == PredictionStatus.UNRESOLVED
    assert pred.confidence == 0.0
    assert pred.evidence_url is None


def test_prediction_status_enum():
    assert PredictionStatus.CONFIRMED.value == "confirmed"
    assert PredictionStatus.REFUTED.value == "refuted"
    assert PredictionStatus.UNRESOLVED.value == "unresolved"


def test_source_type_enum():
    assert SourceType.TELEGRAM.value == "telegram"
    assert SourceType.NEWS.value == "news"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'prophet_checker.models'`

- [ ] **Step 3: Implement domain models**

```python
# prediction-tracker/src/prophet_checker/models/__init__.py
from prophet_checker.models.domain import (
    Person,
    PersonSource,
    Prediction,
    PredictionStatus,
    RawDocument,
    SourceType,
)

__all__ = [
    "Person",
    "PersonSource",
    "Prediction",
    "PredictionStatus",
    "RawDocument",
    "SourceType",
]
```

```python
# prediction-tracker/src/prophet_checker/models/domain.py
from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class SourceType(str, Enum):
    TELEGRAM = "telegram"
    NEWS = "news"


class PredictionStatus(str, Enum):
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    UNRESOLVED = "unresolved"


class Person(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class PersonSource(BaseModel):
    id: str
    person_id: str
    source_type: SourceType
    source_identifier: str
    enabled: bool = True


class RawDocument(BaseModel):
    id: str
    person_id: str
    source_type: SourceType
    url: str
    published_at: datetime
    raw_text: str
    language: str = "uk"
    collected_at: datetime = None

    def model_post_init(self, __context) -> None:
        if self.collected_at is None:
            self.collected_at = datetime.utcnow()


class Prediction(BaseModel):
    id: str
    document_id: str
    person_id: str
    claim_text: str
    prediction_date: date
    target_date: date | None = None
    topic: str = ""
    status: PredictionStatus = PredictionStatus.UNRESOLVED
    confidence: float = 0.0
    evidence_url: str | None = None
    evidence_text: str | None = None
    verified_at: datetime | None = None
    embedding: list[float] | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/models/ tests/test_models.py
git commit -m "feat: add Pydantic domain models (Person, PersonSource, RawDocument, Prediction)"
git push
```

**🏁 End of Task 2.** STOP. Show summary to user. Wait for explicit approval before Task 3.

---

## Task 3: Storage Interfaces ✅ COMPLETE (commit 035468e)

**Files:**
- Create: `prediction-tracker/src/prophet_checker/storage/__init__.py`
- Create: `prediction-tracker/src/prophet_checker/storage/interfaces.py`
- Create: `prediction-tracker/tests/test_storage_interfaces.py`

- [ ] **Step 1: Write tests for storage interfaces**

```python
# prediction-tracker/tests/test_storage_interfaces.py
from datetime import date, datetime
from prophet_checker.storage.interfaces import (
    PersonRepository,
    PredictionRepository,
    SourceRepository,
    VectorStore,
)
from prophet_checker.models.domain import (
    Person,
    PersonSource,
    Prediction,
    PredictionStatus,
    RawDocument,
    SourceType,
)


class FakePersonRepo(PersonRepository):
    def __init__(self):
        self._persons: dict[str, Person] = {}

    async def save(self, person: Person) -> Person:
        self._persons[person.id] = person
        return person

    async def get_by_id(self, person_id: str) -> Person | None:
        return self._persons.get(person_id)

    async def list_all(self) -> list[Person]:
        return list(self._persons.values())


class FakeSourceRepo(SourceRepository):
    def __init__(self):
        self._sources: list[PersonSource] = []
        self._documents: list[RawDocument] = []

    async def save_person_source(self, ps: PersonSource) -> PersonSource:
        self._sources.append(ps)
        return ps

    async def get_person_sources(self, person_id: str, source_type: SourceType | None = None) -> list[PersonSource]:
        return [s for s in self._sources if s.person_id == person_id and (source_type is None or s.source_type == source_type)]

    async def save_document(self, doc: RawDocument) -> RawDocument:
        self._documents.append(doc)
        return doc

    async def get_document_by_url(self, url: str) -> RawDocument | None:
        return next((d for d in self._documents if d.url == url), None)

    async def get_unprocessed_documents(self) -> list[RawDocument]:
        return self._documents

    async def get_last_collected_at(self, person_id: str, source_type: SourceType) -> datetime | None:
        docs = [d for d in self._documents if d.person_id == person_id and d.source_type == source_type]
        if not docs:
            return None
        return max(d.collected_at for d in docs)


class FakePredictionRepo(PredictionRepository):
    def __init__(self):
        self._predictions: list[Prediction] = []

    async def save(self, prediction: Prediction) -> Prediction:
        self._predictions.append(prediction)
        return prediction

    async def get_by_person(self, person_id: str, status: PredictionStatus | None = None) -> list[Prediction]:
        return [
            p for p in self._predictions
            if p.person_id == person_id and (status is None or p.status == status)
        ]

    async def get_unverified(self) -> list[Prediction]:
        return [p for p in self._predictions if p.status == PredictionStatus.UNRESOLVED and p.verified_at is None]

    async def update(self, prediction: Prediction) -> Prediction:
        self._predictions = [p if p.id != prediction.id else prediction for p in self._predictions]
        return prediction


class FakeVectorStore(VectorStore):
    def __init__(self):
        self._entries: list[tuple[str, list[float]]] = []

    async def store_embedding(self, prediction_id: str, embedding: list[float]) -> None:
        self._entries.append((prediction_id, embedding))

    async def search_similar(self, query_embedding: list[float], limit: int = 10) -> list[str]:
        return [pid for pid, _ in self._entries[:limit]]


async def test_person_repo_round_trip():
    repo = FakePersonRepo()
    person = Person(id="1", name="Арестович", description="Оглядач")
    await repo.save(person)
    result = await repo.get_by_id("1")
    assert result is not None
    assert result.name == "Арестович"


async def test_source_repo_save_and_query():
    repo = FakeSourceRepo()
    ps = PersonSource(id="1", person_id="1", source_type=SourceType.TELEGRAM, source_identifier="@arest")
    await repo.save_person_source(ps)
    sources = await repo.get_person_sources("1", SourceType.TELEGRAM)
    assert len(sources) == 1
    assert sources[0].source_identifier == "@arest"


async def test_source_repo_last_collected_at():
    repo = FakeSourceRepo()
    doc1 = RawDocument(id="1", person_id="1", source_type=SourceType.TELEGRAM, url="u1",
                       published_at=datetime(2023, 1, 1), raw_text="text",
                       collected_at=datetime(2024, 1, 1))
    doc2 = RawDocument(id="2", person_id="1", source_type=SourceType.TELEGRAM, url="u2",
                       published_at=datetime(2023, 2, 1), raw_text="text",
                       collected_at=datetime(2024, 2, 1))
    await repo.save_document(doc1)
    await repo.save_document(doc2)
    last = await repo.get_last_collected_at("1", SourceType.TELEGRAM)
    assert last == datetime(2024, 2, 1)


async def test_source_repo_last_collected_at_empty():
    repo = FakeSourceRepo()
    last = await repo.get_last_collected_at("1", SourceType.TELEGRAM)
    assert last is None


async def test_prediction_repo_save_and_query():
    repo = FakePredictionRepo()
    pred = Prediction(id="1", document_id="d1", person_id="1",
                      claim_text="Test prediction", prediction_date=date(2023, 1, 1))
    await repo.save(pred)
    results = await repo.get_by_person("1")
    assert len(results) == 1
    assert results[0].claim_text == "Test prediction"


async def test_prediction_repo_filter_by_status():
    repo = FakePredictionRepo()
    p1 = Prediction(id="1", document_id="d1", person_id="1",
                    claim_text="Pred 1", prediction_date=date(2023, 1, 1),
                    status=PredictionStatus.CONFIRMED)
    p2 = Prediction(id="2", document_id="d2", person_id="1",
                    claim_text="Pred 2", prediction_date=date(2023, 2, 1),
                    status=PredictionStatus.REFUTED)
    await repo.save(p1)
    await repo.save(p2)
    confirmed = await repo.get_by_person("1", status=PredictionStatus.CONFIRMED)
    assert len(confirmed) == 1
    assert confirmed[0].id == "1"


async def test_vector_store_search():
    store = FakeVectorStore()
    await store.store_embedding("p1", [0.1, 0.2, 0.3])
    await store.store_embedding("p2", [0.4, 0.5, 0.6])
    results = await store.search_similar([0.1, 0.2, 0.3], limit=1)
    assert len(results) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_storage_interfaces.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'prophet_checker.storage'`

- [ ] **Step 3: Implement storage interfaces**

```python
# prediction-tracker/src/prophet_checker/storage/__init__.py
from prophet_checker.storage.interfaces import (
    PersonRepository,
    PredictionRepository,
    SourceRepository,
    VectorStore,
)

__all__ = ["PersonRepository", "PredictionRepository", "SourceRepository", "VectorStore"]
```

```python
# prediction-tracker/src/prophet_checker/storage/interfaces.py
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from prophet_checker.models.domain import (
    Person,
    PersonSource,
    Prediction,
    PredictionStatus,
    RawDocument,
    SourceType,
)


class PersonRepository(Protocol):
    async def save(self, person: Person) -> Person: ...
    async def get_by_id(self, person_id: str) -> Person | None: ...
    async def list_all(self) -> list[Person]: ...


class SourceRepository(Protocol):
    async def save_person_source(self, ps: PersonSource) -> PersonSource: ...
    async def get_person_sources(
        self, person_id: str, source_type: SourceType | None = None
    ) -> list[PersonSource]: ...
    async def save_document(self, doc: RawDocument) -> RawDocument: ...
    async def get_document_by_url(self, url: str) -> RawDocument | None: ...
    async def get_unprocessed_documents(self) -> list[RawDocument]: ...
    async def get_last_collected_at(
        self, person_id: str, source_type: SourceType
    ) -> datetime | None: ...


class PredictionRepository(Protocol):
    async def save(self, prediction: Prediction) -> Prediction: ...
    async def get_by_person(
        self, person_id: str, status: PredictionStatus | None = None
    ) -> list[Prediction]: ...
    async def get_unverified(self) -> list[Prediction]: ...
    async def update(self, prediction: Prediction) -> Prediction: ...


class VectorStore(Protocol):
    async def store_embedding(self, prediction_id: str, embedding: list[float]) -> None: ...
    async def search_similar(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[str]: ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_storage_interfaces.py -v
```

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/storage/ tests/test_storage_interfaces.py
git commit -m "feat: add storage Protocol interfaces (PersonRepo, SourceRepo, PredictionRepo, VectorStore)"
git push
```

**🏁 End of Task 3.** STOP. Show summary to user. Wait for explicit approval before Task 4.

---

## Task 4: SQLAlchemy ORM Models + Alembic ✅ COMPLETE (commit 1ca8a16)

**Files:**
- Create: `prediction-tracker/src/prophet_checker/models/db.py`
- Create: `prediction-tracker/alembic.ini`
- Create: `prediction-tracker/alembic/env.py`
- Create: `prediction-tracker/alembic/versions/` (directory)

- [ ] **Step 1: Create SQLAlchemy ORM models**

```python
# prediction-tracker/src/prophet_checker/models/db.py
from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PersonDB(Base):
    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sources: Mapped[list[PersonSourceDB]] = relationship(back_populates="person")
    documents: Mapped[list[RawDocumentDB]] = relationship(back_populates="person")
    predictions: Mapped[list[PredictionDB]] = relationship(back_populates="person")


class PersonSourceDB(Base):
    __tablename__ = "person_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    person: Mapped[PersonDB] = relationship(back_populates="sources")


class RawDocumentDB(Base):
    __tablename__ = "raw_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False, unique=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="uk")
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed: Mapped[bool] = mapped_column(Boolean, default=False)

    person: Mapped[PersonDB] = relationship(back_populates="documents")
    predictions: Mapped[list[PredictionDB]] = relationship(back_populates="document")


class PredictionDB(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("raw_documents.id"), nullable=False)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    prediction_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    topic: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="unresolved")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)

    document: Mapped[RawDocumentDB] = relationship(back_populates="predictions")
    person: Mapped[PersonDB] = relationship(back_populates="predictions")
```

- [ ] **Step 2: Create Alembic configuration**

```bash
mkdir -p prediction-tracker/alembic/versions
```

```ini
# prediction-tracker/alembic.ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

```python
# prediction-tracker/alembic/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from prophet_checker.models.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 3: Verify ORM models import cleanly**

```bash
python -c "from prophet_checker.models.db import Base, PersonDB, PersonSourceDB, RawDocumentDB, PredictionDB; print('OK:', len(Base.metadata.tables), 'tables')"
```

Expected: `OK: 4 tables`

- [ ] **Step 4: Commit**

```bash
git add src/prophet_checker/models/db.py alembic.ini alembic/
git commit -m "feat: add SQLAlchemy ORM models and Alembic config"
git push
```

**🏁 End of Task 4. Milestone M1 complete!** STOP. Show summary to user. Wait for explicit approval before M2.

---

## Task 5: PostgreSQL Storage Implementation ✅ COMPLETE (commit cd25af0)

**Files:**
- Create: `prediction-tracker/src/prophet_checker/storage/postgres.py`
- Create: `prediction-tracker/tests/test_storage_postgres.py`

- [ ] **Step 1: Write tests for PostgreSQL storage**

These tests use an in-memory approach — they test the mapping logic between domain models and DB models, not the actual DB. Full integration tests require a running PostgreSQL (deferred to Docker setup in Task 11).

```python
# prediction-tracker/tests/test_storage_postgres.py
from datetime import date, datetime
from prophet_checker.models.domain import (
    Person, PersonSource, Prediction, PredictionStatus, RawDocument, SourceType,
)
from prophet_checker.storage.postgres import (
    domain_to_person_db, person_db_to_domain,
    domain_to_person_source_db, person_source_db_to_domain,
    domain_to_raw_document_db, raw_document_db_to_domain,
    domain_to_prediction_db, prediction_db_to_domain,
)
from prophet_checker.models.db import PersonDB, PersonSourceDB, RawDocumentDB, PredictionDB


def test_person_domain_to_db():
    person = Person(id="1", name="Арестович", description="Оглядач")
    db_obj = domain_to_person_db(person)
    assert isinstance(db_obj, PersonDB)
    assert db_obj.id == "1"
    assert db_obj.name == "Арестович"


def test_person_db_to_domain():
    db_obj = PersonDB(id="1", name="Арестович", description="Оглядач", created_at=datetime(2024, 1, 1))
    domain_obj = person_db_to_domain(db_obj)
    assert isinstance(domain_obj, Person)
    assert domain_obj.name == "Арестович"


def test_person_source_round_trip():
    ps = PersonSource(id="1", person_id="p1", source_type=SourceType.TELEGRAM,
                      source_identifier="@chan", enabled=True)
    db_obj = domain_to_person_source_db(ps)
    assert db_obj.source_type == "telegram"
    result = person_source_db_to_domain(db_obj)
    assert result.source_type == SourceType.TELEGRAM
    assert result.source_identifier == "@chan"


def test_raw_document_round_trip():
    doc = RawDocument(id="1", person_id="p1", source_type=SourceType.NEWS,
                      url="https://example.com/article", published_at=datetime(2023, 5, 1),
                      raw_text="Some text", language="uk", collected_at=datetime(2024, 1, 1))
    db_obj = domain_to_raw_document_db(doc)
    assert db_obj.source_type == "news"
    assert db_obj.url == "https://example.com/article"
    result = raw_document_db_to_domain(db_obj)
    assert result.source_type == SourceType.NEWS


def test_prediction_round_trip():
    pred = Prediction(id="1", document_id="d1", person_id="p1",
                      claim_text="Test claim", prediction_date=date(2023, 1, 1),
                      target_date=date(2023, 6, 1), topic="війна",
                      status=PredictionStatus.CONFIRMED, confidence=0.85,
                      evidence_url="https://news.com/proof", evidence_text="Proof text")
    db_obj = domain_to_prediction_db(pred)
    assert db_obj.status == "confirmed"
    assert db_obj.confidence == 0.85
    result = prediction_db_to_domain(db_obj)
    assert result.status == PredictionStatus.CONFIRMED
    assert result.evidence_url == "https://news.com/proof"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_storage_postgres.py -v
```

Expected: FAIL — `ImportError: cannot import name 'domain_to_person_db'`

- [ ] **Step 3: Implement PostgreSQL storage with mappers**

```python
# prediction-tracker/src/prophet_checker/storage/postgres.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from prophet_checker.models.db import (
    PersonDB, PersonSourceDB, PredictionDB, RawDocumentDB,
)
from prophet_checker.models.domain import (
    Person, PersonSource, Prediction, PredictionStatus, RawDocument, SourceType,
)


# --- Mappers: Domain <-> DB ---

def domain_to_person_db(person: Person) -> PersonDB:
    return PersonDB(
        id=person.id, name=person.name, description=person.description,
        created_at=person.created_at,
    )


def person_db_to_domain(db: PersonDB) -> Person:
    return Person(id=db.id, name=db.name, description=db.description, created_at=db.created_at)


def domain_to_person_source_db(ps: PersonSource) -> PersonSourceDB:
    return PersonSourceDB(
        id=ps.id, person_id=ps.person_id, source_type=ps.source_type.value,
        source_identifier=ps.source_identifier, enabled=ps.enabled,
    )


def person_source_db_to_domain(db: PersonSourceDB) -> PersonSource:
    return PersonSource(
        id=db.id, person_id=db.person_id, source_type=SourceType(db.source_type),
        source_identifier=db.source_identifier, enabled=db.enabled,
    )


def domain_to_raw_document_db(doc: RawDocument) -> RawDocumentDB:
    return RawDocumentDB(
        id=doc.id, person_id=doc.person_id, source_type=doc.source_type.value,
        url=doc.url, published_at=doc.published_at, raw_text=doc.raw_text,
        language=doc.language, collected_at=doc.collected_at, processed=False,
    )


def raw_document_db_to_domain(db: RawDocumentDB) -> RawDocument:
    return RawDocument(
        id=db.id, person_id=db.person_id, source_type=SourceType(db.source_type),
        url=db.url, published_at=db.published_at, raw_text=db.raw_text,
        language=db.language, collected_at=db.collected_at,
    )


def domain_to_prediction_db(pred: Prediction) -> PredictionDB:
    return PredictionDB(
        id=pred.id, document_id=pred.document_id, person_id=pred.person_id,
        claim_text=pred.claim_text, prediction_date=pred.prediction_date,
        target_date=pred.target_date, topic=pred.topic,
        status=pred.status.value, confidence=pred.confidence,
        evidence_url=pred.evidence_url, evidence_text=pred.evidence_text,
        verified_at=pred.verified_at, embedding=pred.embedding,
    )


def prediction_db_to_domain(db: PredictionDB) -> Prediction:
    return Prediction(
        id=db.id, document_id=db.document_id, person_id=db.person_id,
        claim_text=db.claim_text, prediction_date=db.prediction_date,
        target_date=db.target_date, topic=db.topic,
        status=PredictionStatus(db.status), confidence=db.confidence,
        evidence_url=db.evidence_url, evidence_text=db.evidence_text,
        verified_at=db.verified_at,
    )


# --- Repository implementations ---

class PostgresPersonRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(self, person: Person) -> Person:
        async with self._session_factory() as session:
            db_obj = domain_to_person_db(person)
            session.add(db_obj)
            await session.commit()
            await session.refresh(db_obj)
            return person_db_to_domain(db_obj)

    async def get_by_id(self, person_id: str) -> Person | None:
        async with self._session_factory() as session:
            result = await session.get(PersonDB, person_id)
            return person_db_to_domain(result) if result else None

    async def list_all(self) -> list[Person]:
        async with self._session_factory() as session:
            result = await session.execute(select(PersonDB))
            return [person_db_to_domain(row) for row in result.scalars().all()]


class PostgresSourceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save_person_source(self, ps: PersonSource) -> PersonSource:
        async with self._session_factory() as session:
            db_obj = domain_to_person_source_db(ps)
            session.add(db_obj)
            await session.commit()
            return ps

    async def get_person_sources(
        self, person_id: str, source_type: SourceType | None = None
    ) -> list[PersonSource]:
        async with self._session_factory() as session:
            stmt = select(PersonSourceDB).where(PersonSourceDB.person_id == person_id)
            if source_type is not None:
                stmt = stmt.where(PersonSourceDB.source_type == source_type.value)
            result = await session.execute(stmt)
            return [person_source_db_to_domain(row) for row in result.scalars().all()]

    async def save_document(self, doc: RawDocument) -> RawDocument:
        async with self._session_factory() as session:
            db_obj = domain_to_raw_document_db(doc)
            session.add(db_obj)
            await session.commit()
            return doc

    async def get_document_by_url(self, url: str) -> RawDocument | None:
        async with self._session_factory() as session:
            stmt = select(RawDocumentDB).where(RawDocumentDB.url == url)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return raw_document_db_to_domain(row) if row else None

    async def get_unprocessed_documents(self) -> list[RawDocument]:
        async with self._session_factory() as session:
            stmt = select(RawDocumentDB).where(RawDocumentDB.processed == False)
            result = await session.execute(stmt)
            return [raw_document_db_to_domain(row) for row in result.scalars().all()]

    async def get_last_collected_at(
        self, person_id: str, source_type: SourceType
    ) -> datetime | None:
        async with self._session_factory() as session:
            stmt = select(func.max(RawDocumentDB.collected_at)).where(
                RawDocumentDB.person_id == person_id,
                RawDocumentDB.source_type == source_type.value,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()


class PostgresPredictionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(self, prediction: Prediction) -> Prediction:
        async with self._session_factory() as session:
            db_obj = domain_to_prediction_db(prediction)
            session.add(db_obj)
            await session.commit()
            return prediction

    async def get_by_person(
        self, person_id: str, status: PredictionStatus | None = None
    ) -> list[Prediction]:
        async with self._session_factory() as session:
            stmt = select(PredictionDB).where(PredictionDB.person_id == person_id)
            if status is not None:
                stmt = stmt.where(PredictionDB.status == status.value)
            result = await session.execute(stmt)
            return [prediction_db_to_domain(row) for row in result.scalars().all()]

    async def get_unverified(self) -> list[Prediction]:
        async with self._session_factory() as session:
            stmt = select(PredictionDB).where(
                PredictionDB.status == PredictionStatus.UNRESOLVED.value,
                PredictionDB.verified_at.is_(None),
            )
            result = await session.execute(stmt)
            return [prediction_db_to_domain(row) for row in result.scalars().all()]

    async def update(self, prediction: Prediction) -> Prediction:
        async with self._session_factory() as session:
            db_obj = await session.get(PredictionDB, prediction.id)
            if db_obj:
                db_obj.status = prediction.status.value
                db_obj.confidence = prediction.confidence
                db_obj.evidence_url = prediction.evidence_url
                db_obj.evidence_text = prediction.evidence_text
                db_obj.verified_at = prediction.verified_at
                await session.commit()
            return prediction


class PostgresVectorStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def store_embedding(self, prediction_id: str, embedding: list[float]) -> None:
        async with self._session_factory() as session:
            db_obj = await session.get(PredictionDB, prediction_id)
            if db_obj:
                db_obj.embedding = embedding
                await session.commit()

    async def search_similar(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[str]:
        async with self._session_factory() as session:
            stmt = (
                select(PredictionDB.id)
                .order_by(PredictionDB.embedding.cosine_distance(query_embedding))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_storage_postgres.py -v
```

Expected: 5 tests PASS (mapper tests only — no DB connection needed)

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/storage/postgres.py tests/test_storage_postgres.py
git commit -m "feat: add PostgreSQL storage implementation with domain<->DB mappers"
git push
```

**🏁 End of Task 5.** STOP. Show summary to user. Wait for explicit approval before Task 6.

---

## Task 6: LLM Client ✅ COMPLETE (commit f90eb07)

**Files:**
- Create: `prediction-tracker/src/prophet_checker/llm/__init__.py`
- Create: `prediction-tracker/src/prophet_checker/llm/client.py`
- Create: `prediction-tracker/tests/test_llm_client.py`

- [ ] **Step 1: Write tests for LLM client**

```python
# prediction-tracker/tests/test_llm_client.py
from unittest.mock import AsyncMock, patch
from prophet_checker.llm.client import LLMClient


async def test_llm_client_complete():
    client = LLMClient(provider="openai", model="gpt-4o-mini", api_key="sk-test")
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="Test response"))]

    with patch("prophet_checker.llm.client.acompletion", return_value=mock_response) as mock_call:
        result = await client.complete("Test prompt")
        assert result == "Test response"
        mock_call.assert_called_once()


async def test_llm_client_complete_with_system():
    client = LLMClient(provider="openai", model="gpt-4o-mini", api_key="sk-test")
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="Answer"))]

    with patch("prophet_checker.llm.client.acompletion", return_value=mock_response) as mock_call:
        result = await client.complete("Question", system="You are an analyst")
        assert result == "Answer"
        call_args = mock_call.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are an analyst"


async def test_llm_client_embed():
    client = LLMClient(provider="openai", model="gpt-4o-mini", api_key="sk-test",
                        embedding_model="text-embedding-3-small")
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.1, 0.2, 0.3])]

    with patch("prophet_checker.llm.client.aembedding", return_value=mock_response) as mock_call:
        result = await client.embed("Test text")
        assert result == [0.1, 0.2, 0.3]
        mock_call.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'prophet_checker.llm'`

- [ ] **Step 3: Implement LLM client**

```python
# prediction-tracker/src/prophet_checker/llm/__init__.py
from prophet_checker.llm.client import LLMClient

__all__ = ["LLMClient"]
```

```python
# prediction-tracker/src/prophet_checker/llm/client.py
from __future__ import annotations

from litellm import acompletion, aembedding


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        embedding_model: str = "text-embedding-3-small",
        temperature: float = 0.1,
    ):
        self._model = f"{provider}/{model}" if provider != "openai" else model
        self._embedding_model = embedding_model
        self._api_key = api_key
        self._temperature = temperature

    async def complete(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await acompletion(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            api_key=self._api_key,
        )
        return response.choices[0].message.content

    async def embed(self, text: str) -> list[float]:
        response = await aembedding(
            model=self._embedding_model,
            input=[text],
            api_key=self._api_key,
        )
        return response.data[0].embedding
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_llm_client.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/llm/ tests/test_llm_client.py
git commit -m "feat: add LLM client with LiteLLM abstraction (complete + embed)"
git push
```

**🏁 End of Task 6.** STOP. Show summary to user. Wait for explicit approval before Task 7.

---

## Task 7: Prompt Templates ✅ COMPLETE (commit 006a458)

> **Retrospective:** Note: `EXTRACTION_SYSTEM` was later iterated to v2 in Task 13 to add 6-category NO rules; current production prompt reflects that change.

**Files:**
- Create: `prediction-tracker/src/prophet_checker/llm/prompts.py`
- Create: `prediction-tracker/tests/test_llm_prompts.py`

- [ ] **Step 1: Write tests for prompt templates**

```python
# prediction-tracker/tests/test_llm_prompts.py
import json
from prophet_checker.llm.prompts import (
    build_extraction_prompt,
    build_verification_prompt,
    build_rag_prompt,
    parse_extraction_response,
    parse_verification_response,
)


def test_build_extraction_prompt():
    prompt = build_extraction_prompt(
        text="Контрнаступ почнеться влітку 2023 року",
        person_name="Арестович",
        published_date="2023-01-15",
    )
    assert "Арестович" in prompt
    assert "Контрнаступ почнеться влітку 2023 року" in prompt
    assert "2023-01-15" in prompt
    assert "JSON" in prompt


def test_parse_extraction_response_valid():
    response = json.dumps({
        "predictions": [
            {
                "claim_text": "Контрнаступ почнеться влітку 2023",
                "prediction_date": "2023-01-15",
                "target_date": "2023-06-01",
                "topic": "війна",
            }
        ]
    })
    predictions = parse_extraction_response(response)
    assert len(predictions) == 1
    assert predictions[0]["claim_text"] == "Контрнаступ почнеться влітку 2023"


def test_parse_extraction_response_no_predictions():
    response = json.dumps({"predictions": []})
    predictions = parse_extraction_response(response)
    assert predictions == []


def test_parse_extraction_response_invalid_json():
    predictions = parse_extraction_response("not json at all")
    assert predictions == []


def test_build_verification_prompt():
    prompt = build_verification_prompt(
        claim="Контрнаступ почнеться влітку 2023",
        prediction_date="2023-01-15",
        target_date="2023-06-01",
    )
    assert "Контрнаступ почнеться влітку 2023" in prompt
    assert "JSON" in prompt


def test_parse_verification_response_valid():
    response = json.dumps({
        "status": "confirmed",
        "confidence": 0.85,
        "evidence_url": "https://news.com/article",
        "evidence_text": "The counteroffensive began in June 2023",
    })
    result = parse_verification_response(response)
    assert result["status"] == "confirmed"
    assert result["confidence"] == 0.85


def test_parse_verification_response_invalid_json():
    result = parse_verification_response("broken json")
    assert result is None


def test_build_rag_prompt():
    predictions_context = [
        {"claim_text": "Pred 1", "status": "confirmed", "confidence": 0.9},
        {"claim_text": "Pred 2", "status": "refuted", "confidence": 0.7},
    ]
    prompt = build_rag_prompt(
        question="Що казав Арестович про контрнаступ?",
        predictions_context=predictions_context,
    )
    assert "Що казав Арестович про контрнаступ?" in prompt
    assert "Pred 1" in prompt
    assert "Pred 2" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm_prompts.py -v
```

Expected: FAIL — `ImportError: cannot import name 'build_extraction_prompt'`

- [ ] **Step 3: Implement prompt templates**

```python
# prediction-tracker/src/prophet_checker/llm/prompts.py
from __future__ import annotations

import json


EXTRACTION_SYSTEM = """You are an expert analyst who identifies predictions and forecasts in Ukrainian political commentary. 
Extract specific, verifiable predictions from the given text. 
A prediction is a statement about future events that can be verified as true or false.
Respond ONLY with valid JSON."""

EXTRACTION_TEMPLATE = """Analyze the following text by {person_name} (published on {published_date}).
Extract all predictions — statements about future events that can later be verified.

Text:
---
{text}
---

For each prediction, extract:
- claim_text: the exact prediction (in original language)
- prediction_date: when the prediction was made (YYYY-MM-DD)
- target_date: when the predicted event should happen (YYYY-MM-DD or null if unclear)
- topic: category (e.g., "війна", "економіка", "політика", "міжнародні відносини")

Respond with JSON:
{{"predictions": [{{"claim_text": "...", "prediction_date": "...", "target_date": "...", "topic": "..."}}]}}

If no predictions found, respond: {{"predictions": []}}"""


VERIFICATION_SYSTEM = """You are a fact-checker who verifies predictions against known events.
You must provide evidence for your verdict. If you cannot find clear evidence, mark as unresolved.
Respond ONLY with valid JSON."""

VERIFICATION_TEMPLATE = """Verify the following prediction:

Claim: "{claim}"
Made on: {prediction_date}
Expected by: {target_date}

Determine if this prediction came true based on known events.

Respond with JSON:
{{
  "status": "confirmed" | "refuted" | "unresolved",
  "confidence": 0.0 to 1.0,
  "evidence_url": "URL to supporting evidence or null",
  "evidence_text": "Brief explanation of why this status was assigned"
}}"""


RAG_SYSTEM = """You are Prophet Checker, an AI assistant that analyzes predictions made by Ukrainian public figures.
Answer questions based on the provided prediction data. Always cite sources and confidence scores.
Always add a disclaimer that analysis is automated and may contain inaccuracies.
Respond in Ukrainian."""

RAG_TEMPLATE = """Question: {question}

Relevant predictions from the database:
---
{predictions_context}
---

Based on this data, answer the user's question. Include:
- Specific predictions with dates
- Their verification status and confidence
- Overall accuracy statistics if relevant
- Disclaimer about automated analysis"""


def build_extraction_prompt(text: str, person_name: str, published_date: str) -> str:
    return EXTRACTION_TEMPLATE.format(
        text=text, person_name=person_name, published_date=published_date,
    )


def build_verification_prompt(claim: str, prediction_date: str, target_date: str | None) -> str:
    return VERIFICATION_TEMPLATE.format(
        claim=claim, prediction_date=prediction_date,
        target_date=target_date or "not specified",
    )


def build_rag_prompt(question: str, predictions_context: list[dict]) -> str:
    context_str = "\n".join(
        f"- {p['claim_text']} [status: {p['status']}, confidence: {p['confidence']}]"
        for p in predictions_context
    )
    return RAG_TEMPLATE.format(question=question, predictions_context=context_str)


def parse_extraction_response(response: str) -> list[dict]:
    try:
        data = json.loads(response)
        return data.get("predictions", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def parse_verification_response(response: str) -> dict | None:
    try:
        data = json.loads(response)
        if "status" in data and "confidence" in data:
            return data
        return None
    except (json.JSONDecodeError, AttributeError):
        return None


def get_extraction_system() -> str:
    return EXTRACTION_SYSTEM


def get_verification_system() -> str:
    return VERIFICATION_SYSTEM


def get_rag_system() -> str:
    return RAG_SYSTEM
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_llm_prompts.py -v
```

Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/llm/prompts.py tests/test_llm_prompts.py
git commit -m "feat: add prompt templates for extraction, verification, and RAG"
git push
```

**🏁 End of Task 7.** STOP. Show summary to user. Wait for explicit approval before Task 8.

---

## Task 8: Prediction Extractor ✅ COMPLETE (commit 610b0dd)

> **Retrospective:** Note: extractor's broad `try/except: return []` later proved problematic — masked 4 infra failures during Task 13 eval. Future refactor (split CompletionClient/EmbeddingService) was discussed but deferred — see Task 13.5 spec architecture section.

**Files:**
- Create: `prediction-tracker/src/prophet_checker/analysis/__init__.py`
- Create: `prediction-tracker/src/prophet_checker/analysis/extractor.py`
- Create: `prediction-tracker/tests/test_analysis_extractor.py`

- [ ] **Step 1: Write tests**

```python
# prediction-tracker/tests/test_analysis_extractor.py
import json
from datetime import date, datetime
from unittest.mock import AsyncMock

from prophet_checker.analysis.extractor import PredictionExtractor
from prophet_checker.models.domain import RawDocument, SourceType, PredictionStatus


async def test_extractor_extracts_predictions():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=json.dumps({
        "predictions": [
            {
                "claim_text": "Контрнаступ почнеться влітку 2023",
                "prediction_date": "2023-01-15",
                "target_date": "2023-06-01",
                "topic": "війна",
            }
        ]
    }))
    mock_llm.embed = AsyncMock(return_value=[0.1] * 1536)

    extractor = PredictionExtractor(llm_client=mock_llm)

    doc = RawDocument(
        id="d1", person_id="p1", source_type=SourceType.TELEGRAM,
        url="https://t.me/chan/1", published_at=datetime(2023, 1, 15),
        raw_text="Я думаю що контрнаступ почнеться влітку 2023 року",
    )

    predictions = await extractor.extract(doc, person_name="Арестович")

    assert len(predictions) == 1
    assert predictions[0].claim_text == "Контрнаступ почнеться влітку 2023"
    assert predictions[0].person_id == "p1"
    assert predictions[0].document_id == "d1"
    assert predictions[0].status == PredictionStatus.UNRESOLVED
    assert predictions[0].embedding is not None
    assert len(predictions[0].embedding) == 1536


async def test_extractor_handles_no_predictions():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=json.dumps({"predictions": []}))

    extractor = PredictionExtractor(llm_client=mock_llm)

    doc = RawDocument(
        id="d1", person_id="p1", source_type=SourceType.TELEGRAM,
        url="https://t.me/chan/2", published_at=datetime(2023, 1, 15),
        raw_text="Сьогодні гарна погода",
    )

    predictions = await extractor.extract(doc, person_name="Арестович")
    assert predictions == []


async def test_extractor_handles_llm_error():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value="not valid json")

    extractor = PredictionExtractor(llm_client=mock_llm)

    doc = RawDocument(
        id="d1", person_id="p1", source_type=SourceType.TELEGRAM,
        url="https://t.me/chan/3", published_at=datetime(2023, 1, 15),
        raw_text="Some text",
    )

    predictions = await extractor.extract(doc, person_name="Арестович")
    assert predictions == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_analysis_extractor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'prophet_checker.analysis'`

- [ ] **Step 3: Implement prediction extractor**

```python
# prediction-tracker/src/prophet_checker/analysis/__init__.py
from prophet_checker.analysis.extractor import PredictionExtractor
from prophet_checker.analysis.verifier import PredictionVerifier

__all__ = ["PredictionExtractor", "PredictionVerifier"]
```

```python
# prediction-tracker/src/prophet_checker/analysis/extractor.py
from __future__ import annotations

import uuid
from datetime import date

from prophet_checker.llm.client import LLMClient
from prophet_checker.llm.prompts import (
    build_extraction_prompt,
    get_extraction_system,
    parse_extraction_response,
)
from prophet_checker.models.domain import Prediction, PredictionStatus, RawDocument


class PredictionExtractor:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def extract(self, document: RawDocument, person_name: str) -> list[Prediction]:
        prompt = build_extraction_prompt(
            text=document.raw_text,
            person_name=person_name,
            published_date=document.published_at.strftime("%Y-%m-%d"),
        )

        response = await self._llm.complete(prompt, system=get_extraction_system())
        raw_predictions = parse_extraction_response(response)

        predictions = []
        for raw in raw_predictions:
            claim_text = raw.get("claim_text", "")
            if not claim_text:
                continue

            prediction_date_str = raw.get("prediction_date", "")
            try:
                prediction_date = date.fromisoformat(prediction_date_str)
            except ValueError:
                prediction_date = document.published_at.date()

            target_date = None
            target_date_str = raw.get("target_date")
            if target_date_str:
                try:
                    target_date = date.fromisoformat(target_date_str)
                except ValueError:
                    pass

            embedding = await self._llm.embed(claim_text)

            prediction = Prediction(
                id=str(uuid.uuid4()),
                document_id=document.id,
                person_id=document.person_id,
                claim_text=claim_text,
                prediction_date=prediction_date,
                target_date=target_date,
                topic=raw.get("topic", ""),
                status=PredictionStatus.UNRESOLVED,
                confidence=0.0,
                embedding=embedding,
            )
            predictions.append(prediction)

        return predictions
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_analysis_extractor.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/analysis/ tests/test_analysis_extractor.py
git commit -m "feat: add PredictionExtractor with LLM-based prediction extraction"
git push
```

**🏁 End of Task 8.** STOP. Show summary to user. Wait for explicit approval before Task 9.

---

## Task 9: Prediction Verifier ✅ COMPLETE (commit 20746b8)



**Files:**
- Create: `prediction-tracker/src/prophet_checker/analysis/__init__.py`
- Create: `prediction-tracker/src/prophet_checker/analysis/extractor.py`
- Create: `prediction-tracker/tests/test_analysis_extractor.py`

- [ ] **Step 1: Write tests**

```python
# prediction-tracker/tests/test_analysis_extractor.py
import json
from datetime import date, datetime
from unittest.mock import AsyncMock

from prophet_checker.analysis.extractor import PredictionExtractor
from prophet_checker.models.domain import RawDocument, SourceType, PredictionStatus


async def test_extractor_extracts_predictions():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=json.dumps({
        "predictions": [
            {
                "claim_text": "Контрнаступ почнеться влітку 2023",
                "prediction_date": "2023-01-15",
                "target_date": "2023-06-01",
                "topic": "війна",
            }
        ]
    }))
    mock_llm.embed = AsyncMock(return_value=[0.1] * 1536)

    extractor = PredictionExtractor(llm_client=mock_llm)

    doc = RawDocument(
        id="d1", person_id="p1", source_type=SourceType.TELEGRAM,
        url="https://t.me/chan/1", published_at=datetime(2023, 1, 15),
        raw_text="Я думаю що контрнаступ почнеться влітку 2023 року",
    )

    predictions = await extractor.extract(doc, person_name="Арестович")

    assert len(predictions) == 1
    assert predictions[0].claim_text == "Контрнаступ почнеться влітку 2023"
    assert predictions[0].person_id == "p1"
    assert predictions[0].document_id == "d1"
    assert predictions[0].status == PredictionStatus.UNRESOLVED
    assert predictions[0].embedding is not None
    assert len(predictions[0].embedding) == 1536


async def test_extractor_handles_no_predictions():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=json.dumps({"predictions": []}))

    extractor = PredictionExtractor(llm_client=mock_llm)

    doc = RawDocument(
        id="d1", person_id="p1", source_type=SourceType.TELEGRAM,
        url="https://t.me/chan/2", published_at=datetime(2023, 1, 15),
        raw_text="Сьогодні гарна погода",
    )

    predictions = await extractor.extract(doc, person_name="Арестович")
    assert predictions == []


async def test_extractor_handles_llm_error():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value="not valid json")

    extractor = PredictionExtractor(llm_client=mock_llm)

    doc = RawDocument(
        id="d1", person_id="p1", source_type=SourceType.TELEGRAM,
        url="https://t.me/chan/3", published_at=datetime(2023, 1, 15),
        raw_text="Some text",
    )

    predictions = await extractor.extract(doc, person_name="Арестович")
    assert predictions == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_analysis_extractor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'prophet_checker.analysis'`

- [ ] **Step 3: Implement prediction extractor**

```python
# prediction-tracker/src/prophet_checker/analysis/__init__.py
from prophet_checker.analysis.extractor import PredictionExtractor
from prophet_checker.analysis.verifier import PredictionVerifier

__all__ = ["PredictionExtractor", "PredictionVerifier"]
```

```python
# prediction-tracker/src/prophet_checker/analysis/extractor.py
from __future__ import annotations

import uuid
from datetime import date

from prophet_checker.llm.client import LLMClient
from prophet_checker.llm.prompts import (
    build_extraction_prompt,
    get_extraction_system,
    parse_extraction_response,
)
from prophet_checker.models.domain import Prediction, PredictionStatus, RawDocument


class PredictionExtractor:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def extract(self, document: RawDocument, person_name: str) -> list[Prediction]:
        prompt = build_extraction_prompt(
            text=document.raw_text,
            person_name=person_name,
            published_date=document.published_at.strftime("%Y-%m-%d"),
        )

        response = await self._llm.complete(prompt, system=get_extraction_system())
        raw_predictions = parse_extraction_response(response)

        predictions = []
        for raw in raw_predictions:
            claim_text = raw.get("claim_text", "")
            if not claim_text:
                continue

            prediction_date_str = raw.get("prediction_date", "")
            try:
                prediction_date = date.fromisoformat(prediction_date_str)
            except ValueError:
                prediction_date = document.published_at.date()

            target_date = None
            target_date_str = raw.get("target_date")
            if target_date_str:
                try:
                    target_date = date.fromisoformat(target_date_str)
                except ValueError:
                    pass

            embedding = await self._llm.embed(claim_text)

            prediction = Prediction(
                id=str(uuid.uuid4()),
                document_id=document.id,
                person_id=document.person_id,
                claim_text=claim_text,
                prediction_date=prediction_date,
                target_date=target_date,
                topic=raw.get("topic", ""),
                status=PredictionStatus.UNRESOLVED,
                confidence=0.0,
                embedding=embedding,
            )
            predictions.append(prediction)

        return predictions
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_analysis_extractor.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/analysis/ tests/test_analysis_extractor.py
git commit -m "feat: add PredictionExtractor with LLM-based prediction extraction"
git push
```

**🏁 End of Task 8.** STOP. Show summary to user. Wait for explicit approval before Task 9.


- [ ] **Step 1: Write tests**

```python
# prediction-tracker/tests/test_analysis_verifier.py
import json
from datetime import date, datetime
from unittest.mock import AsyncMock

from prophet_checker.analysis.verifier import PredictionVerifier
from prophet_checker.models.domain import Prediction, PredictionStatus


async def test_verifier_confirms_prediction():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=json.dumps({
        "status": "confirmed",
        "confidence": 0.9,
        "evidence_url": "https://news.com/proof",
        "evidence_text": "The event happened as predicted",
    }))

    verifier = PredictionVerifier(llm_client=mock_llm)

    prediction = Prediction(
        id="1", document_id="d1", person_id="p1",
        claim_text="Контрнаступ почнеться влітку 2023",
        prediction_date=date(2023, 1, 15),
        target_date=date(2023, 6, 1),
        topic="війна",
    )

    result = await verifier.verify(prediction)

    assert result.status == PredictionStatus.CONFIRMED
    assert result.confidence == 0.9
    assert result.evidence_url == "https://news.com/proof"
    assert result.verified_at is not None


async def test_verifier_refutes_prediction():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=json.dumps({
        "status": "refuted",
        "confidence": 0.8,
        "evidence_url": "https://news.com/disproof",
        "evidence_text": "The event did not happen",
    }))

    verifier = PredictionVerifier(llm_client=mock_llm)

    prediction = Prediction(
        id="2", document_id="d1", person_id="p1",
        claim_text="Війна закінчиться до кінця 2023",
        prediction_date=date(2023, 3, 1),
        target_date=date(2023, 12, 31),
    )

    result = await verifier.verify(prediction)
    assert result.status == PredictionStatus.REFUTED
    assert result.confidence == 0.8


async def test_verifier_marks_low_confidence_as_unresolved():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=json.dumps({
        "status": "confirmed",
        "confidence": 0.4,
        "evidence_url": None,
        "evidence_text": "Unclear evidence",
    }))

    verifier = PredictionVerifier(llm_client=mock_llm, confidence_threshold=0.6)

    prediction = Prediction(
        id="3", document_id="d1", person_id="p1",
        claim_text="Something vague",
        prediction_date=date(2023, 1, 1),
    )

    result = await verifier.verify(prediction)
    assert result.status == PredictionStatus.UNRESOLVED
    assert result.confidence == 0.4


async def test_verifier_handles_invalid_response():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value="broken json")

    verifier = PredictionVerifier(llm_client=mock_llm)

    prediction = Prediction(
        id="4", document_id="d1", person_id="p1",
        claim_text="Test", prediction_date=date(2023, 1, 1),
    )

    result = await verifier.verify(prediction)
    assert result.status == PredictionStatus.UNRESOLVED
    assert result.verified_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_analysis_verifier.py -v
```

Expected: FAIL — `ImportError: cannot import name 'PredictionVerifier'`

- [ ] **Step 3: Implement prediction verifier**

```python
# prediction-tracker/src/prophet_checker/analysis/verifier.py
from __future__ import annotations

from datetime import datetime

from prophet_checker.llm.client import LLMClient
from prophet_checker.llm.prompts import (
    build_verification_prompt,
    get_verification_system,
    parse_verification_response,
)
from prophet_checker.models.domain import Prediction, PredictionStatus


class PredictionVerifier:
    def __init__(self, llm_client: LLMClient, confidence_threshold: float = 0.6):
        self._llm = llm_client
        self._confidence_threshold = confidence_threshold

    async def verify(self, prediction: Prediction) -> Prediction:
        prompt = build_verification_prompt(
            claim=prediction.claim_text,
            prediction_date=prediction.prediction_date.isoformat(),
            target_date=prediction.target_date.isoformat() if prediction.target_date else None,
        )

        response = await self._llm.complete(prompt, system=get_verification_system())
        result = parse_verification_response(response)

        now = datetime.utcnow()

        if result is None:
            prediction.status = PredictionStatus.UNRESOLVED
            prediction.verified_at = now
            return prediction

        confidence = result.get("confidence", 0.0)
        status_str = result.get("status", "unresolved")

        if confidence < self._confidence_threshold:
            prediction.status = PredictionStatus.UNRESOLVED
        else:
            try:
                prediction.status = PredictionStatus(status_str)
            except ValueError:
                prediction.status = PredictionStatus.UNRESOLVED

        prediction.confidence = confidence
        prediction.evidence_url = result.get("evidence_url")
        prediction.evidence_text = result.get("evidence_text")
        prediction.verified_at = now

        return prediction
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_analysis_verifier.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/analysis/verifier.py tests/test_analysis_verifier.py
git commit -m "feat: add PredictionVerifier with confidence thresholding"
git push
```

**🏁 End of Task 9. Milestone M2 complete!** STOP. Show summary to user. Wait for explicit approval before M3.

---

## Task 10: Збір реальних постів з Telegram ✅ COMPLETE (commit d7c9e5e — 1049 Arestovich posts collected via Telethon)

> **Retrospective:** Note: full corpus `scripts/arestovich/all.json` (5572 posts) collected separately, gitignored. Used for future Task 14 smoke test if revived.

**Files:**
- Create: `prediction-tracker/scripts/collect_telegram_posts.py`
- Create: `prediction-tracker/scripts/sample_posts.json` (генерується скриптом)

**Ціль:** Зібрати 100 реальних постів з публічних Telegram-каналів українських публічних осіб за допомогою Telethon. Ці дані стануть вхідними для smoke test (Task 11).

**Канали-джерела (публічні):**
- `@arestovych` — Олексій Арестович
- `@danilov_mykhailo` — Олексій Данілов (РНБО)
- `@Podolyak_M` — Михайло Подоляк (ОПУ)

**Потрібно:**
- Telegram API credentials (`api_id`, `api_hash`) у `.env`
- Telethon встановлено у `.venv`

- [ ] **Step 1: Створити скрипт збору**

```python
# prediction-tracker/scripts/collect_telegram_posts.py
"""
Collect real posts from public Telegram channels via Telethon.
Usage: python scripts/collect_telegram_posts.py

Requires in .env:
  TELEGRAM_API_ID=<id>
  TELEGRAM_API_HASH=<hash>
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
import os

load_dotenv()

from telethon import TelegramClient

CHANNELS = {
    "@arestovych": "Арестович",
    "@danilov_mykhailo": "Данілов",
    "@Podolyak_M": "Подоляк",
}
POSTS_PER_CHANNEL = 35  # ~100 total
MIN_TEXT_LENGTH = 50     # skip short/media-only posts
OUTPUT = Path(__file__).parent / "sample_posts.json"


async def main():
    api_id = int(os.getenv("TELEGRAM_API_ID", 0))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    if not api_id or not api_hash:
        raise RuntimeError("Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")

    client = TelegramClient("scripts/tg_session", api_id, api_hash)
    await client.start()

    all_posts = []
    for channel, person_name in CHANNELS.items():
        print(f"Collecting from {channel} ({person_name})...")
        collected = 0
        async for msg in client.iter_messages(channel, limit=200):
            if not msg.text or len(msg.text) < MIN_TEXT_LENGTH:
                continue
            all_posts.append({
                "id": f"{channel.strip('@')}_{msg.id}",
                "person_name": person_name,
                "published_at": msg.date.strftime("%Y-%m-%d"),
                "text": msg.text,
            })
            collected += 1
            if collected >= POSTS_PER_CHANNEL:
                break
        print(f"  Got {collected} posts")

    await client.disconnect()

    OUTPUT.write_text(json.dumps(all_posts, ensure_ascii=False, indent=2))
    print(f"\n✅ Saved {len(all_posts)} posts to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Запустити скрипт**

```bash
source .venv/bin/activate
python scripts/collect_telegram_posts.py
```

При першому запуску Telethon попросить ввести номер телефону і код — це одноразова авторизація, сесія зберігається у `scripts/tg_session.session`.

- [ ] **Step 3: Валідувати зібрані дані**

Перевірити `scripts/sample_posts.json`:
- Кількість постів (≥80, ціль 100)
- Розподіл по авторах
- Мова текстів (більшість — українська)
- Чи є реальний різноманітний контент (передбачення, коментарі, аналітика)

- [ ] **Step 4: Commit**

```bash
git add scripts/collect_telegram_posts.py
# sample_posts.json — НЕ комітити (містить чужий контент)
# tg_session.session — НЕ комітити (в .gitignore)
echo "scripts/tg_session.session" >> .gitignore
echo "scripts/sample_posts.json" >> .gitignore
git commit -m "feat: add Telegram post collection script for smoke test data"
git push
```

**🏁 End of Task 10.** STOP. Показати зібрані дані користувачу. Отримати підтвердження перед Task 11.

---

## Task 12: Gold Labels — ручна розмітка 50 постів ✅ COMPLETE (commits 428aea4 → a992e0f)

> **Retrospective:** Originally planned 50 binary labels. Extended to **130 labels** (16 YES / 114 NO) on 2026-04-18 to support Task 13 detection eval — original 3/47 YES/NO split was too skewed for meaningful P/R/F1. Arestovich subset: 97 labels (15 YES / 82 NO, 15.5% — matches predicted base rate). [`docs/annotation-guidelines.md`](../annotation/annotation-guidelines.md) refined with 4 hard-pattern edge cases (timestamp lists, slogans, normative, vague) discovered during annotation.

**Files:**
- Create: `prediction-tracker/docs/annotation-guidelines.md`
- Create: `prediction-tracker/scripts/annotate.py` — допоміжний скрипт для розмітки
- Create: `prediction-tracker/scripts/gold_labels.json` (результат розмітки)

**Ціль:** Створити ground truth для оцінки якості detection. Рівень 1 — binary classification: чи є в тексті хоча б одне передбачення (YES/NO).

- [ ] **Step 1: Написати Annotation Guidelines**

`docs/annotation-guidelines.md` — чіткі правила розмітки щоб забезпечити послідовність:

**YES (є передбачення):**
- Конкретне твердження про майбутню подію ("Війна закінчиться до кінця 2023")
- Прогноз з приблизною датою ("Контрнаступ почнеться влітку")
- Прогноз без дати, але верифікований ("Росія програє цю війну" — можна перевірити пост-фактум)

**NO (нема передбачення):**
- Констатація факту ("Сьогодні обстріляли Харків")
- Думка/оцінка без елементу майбутнього ("Це була помилка командування")
- Намір ("Ми будемо боротись до перемоги")
- Умовне без конкретики ("Якщо дадуть зброю — переможемо")
- Риторичне ("Хто міг подумати?")

**Edge cases:**
- "Думаю, переговори можливі" → NO (занадто розмито)
- "Рубль впаде до 100 за долар" → YES (конкретне, верифіковне)
- "Ми підготовлені краще ніж рік тому" → NO (оцінка теперішнього)

- [ ] **Step 2: Вибрати 50 постів для розмітки**

Рандомна вибірка з `sample_posts.json` (seed=42) — стратифікована по авторах (~17 на канал).

- [ ] **Step 3: Розмітка**

Показати користувачу пости пачками по 10. Для кожного — текст (перші 300 символів) та питання: YES чи NO? Зберегти результат у `scripts/gold_labels.json`:

```json
[
  {"id": "arestovych_1234", "has_prediction": true},
  {"id": "arestovych_1235", "has_prediction": false}
]
```

- [ ] **Step 4: Статистика розмітки**

Порахувати:
- Всього розмічено: 50
- YES: N (X%)
- NO: N (X%)
- Розподіл по авторах

- [ ] **Step 5: Commit**

```bash
git add docs/annotation-guidelines.md scripts/annotate.py
# gold_labels.json — НЕ комітити (в .gitignore, містить суб'єктивні дані)
git commit -m "feat: add annotation guidelines and labeling script for detection eval"
git push
```

**🏁 End of Task 12.** STOP. Показати статистику розмітки. Отримати підтвердження перед Task 13.

---

## Task 13: Detection Evaluation — precision/recall/F1 ✅ COMPLETE (2026-04-20)

> **Retrospective update:** Originally planned as a single-model eval on 50 posts. Expanded during execution into a 5-model × 2-prompt comparison on 97 Arestovich gold posts. Key artifacts and commits below reflect what was actually built and shipped.

**Files (as built):**
- Created: [`scripts/evaluate_detection.py`](../scripts/evaluate_detection.py) — 389 lines, multi-provider eval harness with `--model all-primary`, per-provider `CONCURRENCY_OVERRIDES` + `MIN_CALL_INTERVAL_SECONDS`, `DetectionLLM` wrapper that stubs `.embed()` so non-OpenAI providers can run without embedding endpoint
- Created: [`tests/test_evaluate_detection.py`](../tests/test_evaluate_detection.py) — 303 lines, 17 TDD tests across 4 groups (compute_metrics, classify_post, DetectionLLM, run_evaluation_for_model)
- Created: 10 result JSON files in `scripts/detection_results_*` — 5 v1 baseline (`*_v1_baseline.json`) + 5 v2 iterated
- Modified: `pyproject.toml` — added `"scripts"` to `pythonpath`
- Modified: `.env.example` — multi-provider key template

**Production code touched (separate commit `3635eb0 dev`):**
- `src/prophet_checker/llm/prompts.py` — fence-stripping in `parse_*_response`, v2 `EXTRACTION_SYSTEM` with 6-category NO rules
- `src/prophet_checker/llm/client.py` — `num_retries=3` for transient errors
- `src/prophet_checker/config.py` — `model_config["extra"] = "ignore"` for new env keys

**Goal achieved:** Empirically rank 5 LLMs on detection precision/recall/F1 over 97 gold-labeled Arestovich posts; pick winner for production extraction stage.

**Models evaluated (primary tier):**
- `anthropic/claude-haiku-4-5`
- `openai/gpt-5-mini`
- `gemini/gemini-3.1-flash-lite-preview`
- `deepseek/deepseek-chat`
- `groq/llama-3.3-70b-versatile`

**What actually happened (chronological):**

- [x] **Step 1: Built `evaluate_detection.py` harness** (TDD-first, 17 tests)
  - 4 test groups: pure metrics, classify_post bridge, DetectionLLM wrapper, end-to-end orchestration with DI
  - `compute_metrics(gold, preds) -> dict` — P/R/F1 with zero-division guards (recall=None when no gold positives), raises ValueError on length mismatch
  - `DetectionLLM` wrapper bypasses `embed()` with `[0.0]*1536` stub — required because Gemini/DeepSeek/Groq have no OpenAI-compatible embedding endpoint
  - `_default_extractor_factory(model_id)` parses `provider/model`, looks up env-var API key, builds LLMClient + DetectionLLM + PredictionExtractor

- [x] **Step 2: First Haiku run produced F1=0.0** — silent infrastructure bugs masked as "all NO" classifications. Fixed 4 bugs in succession before getting valid results:
  1. **Markdown fence parsing:** Modern LLMs wrap JSON in ` ```json ... ``` ` fences. `parse_extraction_response` did `json.loads(raw)` → `JSONDecodeError` → `[]`. Extractor's broad `except: return []` swallowed silently. Fix: regex `_strip_code_fence()` + 3 new fence tests in `test_llm_prompts.py`. Preventive: added "Respond ONLY with raw JSON — do NOT wrap in markdown code fences" to `EXTRACTION_SYSTEM`.
  2. **GPT-5 temperature constraint:** GPT-5 family rejects `temperature=0.0`. LiteLLM raises `UnsupportedParamsError` → swallowed by extractor → false NO. Fix: `litellm.drop_params = True` at module load in `evaluate_detection.py`. Trade-off: GPT-5 eval runs at temp=1.0 (stochastic).
  3. **Gemini/Groq rate limits:** Free-tier preview models throttle at low RPM (Gemini ~5-10 RPM; Groq TPM-limited). 41 × 429s on Gemini, 160 × 429s on Groq even with `num_retries=3`. Fix: per-model `MIN_CALL_INTERVAL_SECONDS` (Gemini 7s, Groq 13s) + `CONCURRENCY_OVERRIDES` (1 each) — sequential pacing.
  4. **Settings extra_forbidden:** Pydantic strict mode rejected new env keys (ANTHROPIC_API_KEY etc.) on `Settings()` instantiation. Fix: `model_config["extra"] = "ignore"` in `config.py`.

- [x] **Step 3: v1 baseline matrix on 5 models** (commit `3da94a3`)

  | Model | P | R | F1 | Notes |
  |---|---:|---:|---:|---|
  | Llama 3.3 70B | 0.417 | 1.000 | **0.588** | Open-weight win on baseline |
  | DeepSeek V3.1 | 0.366 | 1.000 | 0.536 | Open-weight #2 |
  | GPT-5-mini | 0.254 | 1.000 | 0.405 | Greedy, high FP |
  | Gemini 3.1 Flash Lite | 0.250 | 0.933 | 0.394 | Throttled |
  | Haiku 4.5 | 0.256 | 0.667 | 0.370 | Only R<1 |

  Insight: precision clustered at 0.25-0.42 across models — strong signal that **prompt was the bottleneck, not model capability**.

- [x] **Step 4: Prompt iteration — v2 `EXTRACTION_SYSTEM`**
  Rewrote system prompt with explicit 3-criteria YES test + 6-category NO rejection rules (slogans, author event announcements, normative `треба/повинно`, vague forward statements, present-rhetoric, questions/calls/metaphors). Each category had inline UA/RU examples to anchor the rubric.
  Archived v1 results: `mv detection_results_*.json -> *_v1_baseline.json`. Re-ran all 5 models with v2 prompt.

- [x] **Step 5: v2 final matrix**

  | Model | P | R | F1 | Δ F1 | Verdict |
  |---|---:|---:|---:|---:|---|
  | **Gemini 3.1 Flash Lite** | 0.778 | 0.933 | **0.848** | **+0.454** | 🏆 Production winner |
  | DeepSeek V3.1 | 0.650 | 0.867 | 0.743 | +0.207 | Strong backup |
  | GPT-5-mini | 0.500 | 1.000 | 0.667 | +0.262 | OK but stochastic + slow |
  | Haiku 4.5 | 0.500 | 0.267 | 0.348 | −0.022 | Over-refused |
  | Llama 3.3 70B | 1.000 | 0.067 | 0.125 | **−0.463** | 💥 Catastrophic over-refusal |

  Gemini crossed the F1 ≥ 0.80 acceptance threshold from the original plan. DeepSeek a strong vendor-diversity backup.
  Cost: ~$0.20 total for all 10 eval runs (5 models × 2 prompts).
  Insight: heuristics-heavy v2 prompt helps strong-reasoning models (Gemini/DeepSeek/GPT-5) but over-constrains smaller ones (Haiku, Llama 3.3 70B) — they default to NO.

- [x] **Step 6: Error analysis**
  25 posts had common FP across all 5 v1-baseline models — systematic LLM bias on Arestovich's slogan-heavy style. v2 rules targeted exactly these patterns; FP dropped from 21-44 (v1) to 4-26 (v2) on top-3 models.

- [x] **Step 7: Commit + ship**
  - `3635eb0 dev` — production code fixes (parser, client retries, config)
  - `3da94a3 feat: detection evaluation harness + 5-model P/R/F1 results (Task 13)` — eval harness + 10 result JSONs + tests
  - `4? feat: Sonnet/Opus eval session in flight` — Task 13.5 follow-up (extraction quality, separate plan)

**Production decision:** Gemini 3.1 Flash Lite + v2 prompt for production extraction stage. Estimated cost on full 5572-post Arestovich corpus: ~$0.52 paid tier.

**Outstanding open items:**
- Detection F1 ≥ 0.80 only for 1/5 models. Whether prompt should be model-specific (lighter version for smaller models) — deferred. Solo project: Gemini wins, no need to make Llama/Haiku work.
- Extraction quality (claim_text faithfulness, hallucination, coverage) — NOT measured in Task 13. Spawned **[Task 13.5: Extraction Quality Eval](../extraction-quality-eval/2026-04-21-extraction-quality-eval-plan.md)** with LLM-as-judge approach.

**🏁 Task 13 closed.** Continue to Task 13.5 (extraction quality) before Task 14 smoke test.

---

## Task 13.5: Extraction Quality Evaluation 📋 PLANNED

> **Why this exists:** Task 13 measured **detection** quality (binary YES/NO match against gold labels). It did NOT verify whether `claim_text`, dates, or topics extracted by the model were faithful to the source post. Task 13.5 closes that gap with an LLM-as-judge evaluation.

**Approach:** 3-stage pipeline — Stage 1 captures full extraction outputs from 3 models (Gemini 3.1 Flash Lite, DeepSeek V3.1, Sonnet 4.6); Stage 2 invokes Claude Opus 4.6 as judge to assign 6-value categorical verdicts (`exact_match` / `faithful_paraphrase` / `valid_but_metadata_error` / `not_a_prediction` / `truncated` / `hallucination`) to each extracted claim; Stage 3 aggregates per-model metrics including hallucination rate, missed predictions, and gold-label agreement matrix.

**Files (specs):**
- Spec: [`2026-04-21-extraction-quality-eval-design.md`](../extraction-quality-eval/2026-04-21-extraction-quality-eval-design.md) (commit `403f2fb`)
- Implementation plan: [`2026-04-21-extraction-quality-eval-plan.md`](../extraction-quality-eval/2026-04-21-extraction-quality-eval-plan.md) (commit `ee0b052`) — 10 detailed tasks, ~27 TDD tests, no production code changes

**Files (will be created during execution):**
- `scripts/extraction_judge_prompts.py` — judge SYSTEM/USER templates, 6-value verdict enum, parse helpers
- `scripts/extraction_quality_eval.py` — 3 stage runners + aggregate_metrics + CLI
- `tests/test_extraction_quality_eval.py` — ~27 tests across 3 groups
- `scripts/extraction_outputs.json` (Stage 1 artifact)
- `scripts/extraction_judgements.json` (Stage 2 artifact)
- `scripts/extraction_eval_report.json` (Stage 3 artifact)

**Reuse from Task 13** (no production code changes):
- `DetectionLLM` wrapper — skip embeddings (same infra reasons)
- `_default_extractor_factory` — provider/key wiring
- `CONCURRENCY_OVERRIDES` + `MIN_CALL_INTERVAL_SECONDS` — rate-limit safety
- `EXTRACTION_SYSTEM` v2 — current production prompt
- Annotation guidelines — embedded in judge SYSTEM prompt for consistent rubric

**Budget:** ~$14.38 (extraction $1.28 + Opus judge $13.10). Wall ~2-3 hours.

**Acceptance criteria:**
- All ~27 tests pass
- 3 JSON artifacts generated
- `avg_quality_score` per model computed (ordinal mapping 0-3)
- `hallucination_rate` distinguishes models
- `gold_agreement` matrix populated (cross-tab judge verdicts vs our gold labels)
- No regression in existing 63 tests

**Implementation steps:** see [implementation plan](../extraction-quality-eval/2026-04-21-extraction-quality-eval-plan.md). Decomposed into 4 milestones (M1 pure functions / M2 stage runners / M3 CLI+integration / M4 real run).

**🏁 End of Task 13.5.** STOP. Report final metrics + production decision (which model wins extraction quality, ranked alongside Task 13 detection F1). Brainstorm next steps with user (LinkedIn post / Task 14 revival / proceed to M3 Orchestration).

---

## Task 14: Smoke Test — extraction на повному датасеті ⏸ DEFERRED (2026-04-21 — user decision)

> **Retrospective:** Smoke test on full 5572-post Arestovich corpus deferred. Rationale: Task 13's 97×5×2 eval already provided ~970 extraction calls of empirical signal — additional infrastructure-scaling validation is ceremonial for solo pet project. May revive when ingestion pipeline (Task 15) is built and we have natural reason to process the full corpus.

**Files:**
- Create: `prediction-tracker/scripts/smoke_test.py`
- Create: `prediction-tracker/scripts/smoke_results.json` (генерується)

**Ціль:** Запустити PredictionExtractor на всіх 1049 постах. Після того як detection якість підтверджена на 50 постах — масштабний прогін.

**Вхідні дані:** `scripts/sample_posts.json` (1049 постів, Task 10)

**Вибір моделі:** Визначається за результатами Task 12 (якість vs вартість).

- [ ] **Step 1: Створити smoke test скрипт**

`scripts/smoke_test.py`:
1. Зчитати всі пости з `sample_posts.json`
2. Для кожного: викликати PredictionExtractor (без embeddings для економії)
3. Зберегти результати: post_id, predictions_found, claims, topics
4. Вивести статистику: total posts, total predictions, avg per post, errors, time, estimated cost

- [ ] **Step 2: Запустити**
- [ ] **Step 3: Проаналізувати результати**
- [ ] **Step 4: Записати висновки в `docs/progress.md`**
- [ ] **Step 5: Commit**

**🏁 End of Task 14.** STOP. Проаналізуй результати з користувачем. Отримай явне підтвердження перед Task 15.

---

## Task 15: Ingestion Pipeline Orchestrator 📋 PLANNED


**Files:**
- Create: `prediction-tracker/src/prophet_checker/ingestion.py`
- Create: `prediction-tracker/tests/test_ingestion.py`

- [ ] **Step 1: Write tests**

```python
# prediction-tracker/tests/test_ingestion.py
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from prophet_checker.ingestion import IngestionPipeline
from prophet_checker.models.domain import (
    Person, PersonSource, Prediction, PredictionStatus, RawDocument, SourceType,
)


async def test_ingestion_pipeline_collect_and_extract():
    # Setup mocks
    person = Person(id="p1", name="Арестович")
    person_source = PersonSource(
        id="ps1", person_id="p1", source_type=SourceType.TELEGRAM,
        source_identifier="@arestovych", enabled=True,
    )

    doc = RawDocument(
        id="d1", person_id="p1", source_type=SourceType.TELEGRAM,
        url="https://t.me/arestovych/1", published_at=datetime(2023, 6, 15),
        raw_text="Контрнаступ буде влітку",
    )

    pred = Prediction(
        id="pred1", document_id="d1", person_id="p1",
        claim_text="Контрнаступ буде влітку",
        prediction_date=date(2023, 6, 15),
        embedding=[0.1] * 1536,
    )

    person_repo = AsyncMock()
    person_repo.list_all = AsyncMock(return_value=[person])

    source_repo = AsyncMock()
    source_repo.get_person_sources = AsyncMock(return_value=[person_source])
    source_repo.get_last_collected_at = AsyncMock(return_value=None)
    source_repo.save_document = AsyncMock(return_value=doc)
    source_repo.get_document_by_url = AsyncMock(return_value=None)

    prediction_repo = AsyncMock()
    prediction_repo.save = AsyncMock(return_value=pred)

    vector_store = AsyncMock()
    vector_store.store_embedding = AsyncMock()

    collector = AsyncMock()
    collector.collect = AsyncMock(return_value=[doc])

    extractor = AsyncMock()
    extractor.extract = AsyncMock(return_value=[pred])

    pipeline = IngestionPipeline(
        person_repo=person_repo,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        vector_store=vector_store,
        collectors={SourceType.TELEGRAM: collector},
        extractor=extractor,
    )

    await pipeline.run_collection()

    source_repo.save_document.assert_called_once()
    extractor.extract.assert_called_once()
    prediction_repo.save.assert_called_once()
    vector_store.store_embedding.assert_called_once()


async def test_ingestion_pipeline_skips_existing_documents():
    person = Person(id="p1", name="Test")
    person_source = PersonSource(
        id="ps1", person_id="p1", source_type=SourceType.TELEGRAM,
        source_identifier="@chan", enabled=True,
    )
    existing_doc = RawDocument(
        id="d1", person_id="p1", source_type=SourceType.TELEGRAM,
        url="https://t.me/chan/1", published_at=datetime(2023, 1, 1),
        raw_text="Already collected",
    )

    person_repo = AsyncMock()
    person_repo.list_all = AsyncMock(return_value=[person])

    source_repo = AsyncMock()
    source_repo.get_person_sources = AsyncMock(return_value=[person_source])
    source_repo.get_last_collected_at = AsyncMock(return_value=None)
    source_repo.get_document_by_url = AsyncMock(return_value=existing_doc)

    prediction_repo = AsyncMock()
    vector_store = AsyncMock()

    collector = AsyncMock()
    collector.collect = AsyncMock(return_value=[existing_doc])

    extractor = AsyncMock()

    pipeline = IngestionPipeline(
        person_repo=person_repo,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        vector_store=vector_store,
        collectors={SourceType.TELEGRAM: collector},
        extractor=extractor,
    )

    await pipeline.run_collection()

    source_repo.save_document.assert_not_called()
    extractor.extract.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ingestion.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'prophet_checker.ingestion'`

- [ ] **Step 3: Implement ingestion pipeline**

```python
# prediction-tracker/src/prophet_checker/ingestion.py
from __future__ import annotations

import logging
from datetime import date, datetime

from prophet_checker.analysis.extractor import PredictionExtractor
from prophet_checker.models.domain import SourceType
from prophet_checker.sources.interface import Source
from prophet_checker.storage.interfaces import (
    PersonRepository,
    PredictionRepository,
    SourceRepository,
    VectorStore,
)

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(
        self,
        person_repo: PersonRepository,
        source_repo: SourceRepository,
        prediction_repo: PredictionRepository,
        vector_store: VectorStore,
        collectors: dict[SourceType, Source],
        extractor: PredictionExtractor,
    ):
        self._person_repo = person_repo
        self._source_repo = source_repo
        self._prediction_repo = prediction_repo
        self._vector_store = vector_store
        self._collectors = collectors
        self._extractor = extractor

    async def run_collection(self, date_from: date | None = None) -> None:
        if date_from is None:
            date_from = date(2012, 1, 1)

        persons = await self._person_repo.list_all()

        for person in persons:
            for source_type, collector in self._collectors.items():
                sources = await self._source_repo.get_person_sources(
                    person.id, source_type
                )
                for ps in sources:
                    if not ps.enabled:
                        continue

                    last_collected = await self._source_repo.get_last_collected_at(
                        person.id, source_type
                    )
                    effective_from = last_collected.date() if last_collected else date_from

                    logger.info(
                        "Collecting %s for %s from %s since %s",
                        source_type.value, person.name, ps.source_identifier, effective_from,
                    )

                    documents = await collector.collect(
                        person_id=person.id,
                        channel=ps.source_identifier,
                        date_from=effective_from,
                        date_to=date.today(),
                    )

                    for doc in documents:
                        existing = await self._source_repo.get_document_by_url(doc.url)
                        if existing is not None:
                            continue

                        await self._source_repo.save_document(doc)

                        predictions = await self._extractor.extract(doc, person.name)
                        for pred in predictions:
                            await self._prediction_repo.save(pred)
                            if pred.embedding:
                                await self._vector_store.store_embedding(
                                    pred.id, pred.embedding
                                )

                    logger.info(
                        "Collected %d documents for %s from %s",
                        len(documents), person.name, ps.source_identifier,
                    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ingestion.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/ingestion.py tests/test_ingestion.py
git commit -m "feat: add IngestionPipeline orchestrator for collection + extraction"
git push
```

**🏁 End of Task 15.** STOP. Show summary to user. Wait for explicit approval before Task 16.

---

## Task 16: FastAPI Application Entry Point 📋 PLANNED

**Files:**
- Create: `prediction-tracker/src/prophet_checker/main.py`

- [ ] **Step 1: Create the FastAPI app with health endpoint**

```python
# prediction-tracker/src/prophet_checker/main.py
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from prophet_checker.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.settings = settings
    yield
    await engine.dispose()


app = FastAPI(title="Prophet Checker", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Verify it starts**

```bash
python -c "from prophet_checker.main import app; print('App created:', app.title)"
```

Expected: `App created: Prophet Checker`

- [ ] **Step 3: Commit**

```bash
git add src/prophet_checker/main.py
git commit -m "feat: add FastAPI entry point with health endpoint"
git push
```

**🏁 End of Task 16. Milestone M3 complete!** STOP. Show summary to user. Wait for explicit approval before M4.

---

## Task 17: Docker + Docker Compose 📋 PLANNED

**Files:**
- Create: `prediction-tracker/Dockerfile`
- Create: `prediction-tracker/docker-compose.yml`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
# prediction-tracker/Dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

EXPOSE 8000

CMD ["uvicorn", "prophet_checker.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
# prediction-tracker/docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: prophet
      POSTGRES_PASSWORD: prophet
      POSTGRES_DB: prophet_checker
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://prophet:prophet@db:5432/prophet_checker
      LLM_PROVIDER: ${LLM_PROVIDER:-openai}
      LLM_MODEL: ${LLM_MODEL:-gpt-4o-mini}
      LLM_API_KEY: ${LLM_API_KEY}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      TELEGRAM_API_ID: ${TELEGRAM_API_ID}
      TELEGRAM_API_HASH: ${TELEGRAM_API_HASH}
    depends_on:
      - db

volumes:
  pgdata:
```

- [ ] **Step 3: Verify Docker build**

```bash
docker compose build
```

Expected: Build completes successfully

- [ ] **Step 4: Verify Docker Compose starts**

```bash
docker compose up -d db
docker compose run --rm app python -c "from prophet_checker.main import app; print('OK')"
docker compose down
```

Expected: prints `OK`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: add Docker and docker-compose with pgvector"
git push
```

**🏁 End of Task 17.** STOP. Show summary to user. Wait for explicit approval before Task 18.

---

## Task 18: Run Alembic Migration 📋 PLANNED

**Files:**
- Modify: `prediction-tracker/alembic.ini` (URL from env)

- [ ] **Step 1: Start database**

```bash
docker compose up -d db
```

- [ ] **Step 2: Generate initial migration**

```bash
DATABASE_URL=postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker \
alembic revision --autogenerate -m "initial schema"
```

Expected: Creates migration file in `alembic/versions/`

- [ ] **Step 3: Apply migration**

```bash
DATABASE_URL=postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker \
alembic upgrade head
```

Expected: Migration applies successfully, creates 4 tables

- [ ] **Step 4: Verify tables exist**

```bash
docker compose exec db psql -U prophet -d prophet_checker -c "\dt"
```

Expected: Shows `persons`, `person_sources`, `raw_documents`, `predictions`, `alembic_version`

- [ ] **Step 5: Commit**

```bash
git add alembic/
git commit -m "feat: add initial Alembic migration for all tables"
git push
```

---

## Task 19: Integration Smoke Test 📋 PLANNED

**Files:**
- Create: `prediction-tracker/tests/test_integration.py`

- [ ] **Step 1: Write integration test**

This test requires a running PostgreSQL (via Docker Compose). Mark it so it can be skipped in CI without DB.

```python
# prediction-tracker/tests/test_integration.py
import os
import uuid
from datetime import date, datetime

import pytest

from prophet_checker.models.domain import (
    Person, PersonSource, Prediction, PredictionStatus, RawDocument, SourceType,
)

DB_URL = os.getenv("DATABASE_URL", "")
requires_db = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")


@requires_db
async def test_full_storage_round_trip():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from prophet_checker.storage.postgres import (
        PostgresPersonRepository, PostgresSourceRepository,
        PostgresPredictionRepository, PostgresVectorStore,
    )

    engine = create_async_engine(DB_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    person_repo = PostgresPersonRepository(session_factory)
    source_repo = PostgresSourceRepository(session_factory)
    pred_repo = PostgresPredictionRepository(session_factory)

    # Create person
    person_id = str(uuid.uuid4())
    person = await person_repo.save(
        Person(id=person_id, name="Test Person", description="Integration test")
    )
    assert person.name == "Test Person"

    # Create person source
    await source_repo.save_person_source(
        PersonSource(
            id=str(uuid.uuid4()), person_id=person_id,
            source_type=SourceType.TELEGRAM, source_identifier="@test_chan",
        )
    )
    sources = await source_repo.get_person_sources(person_id, SourceType.TELEGRAM)
    assert len(sources) == 1

    # Create document
    doc_id = str(uuid.uuid4())
    doc_url = f"https://t.me/test/{uuid.uuid4().hex[:8]}"
    await source_repo.save_document(
        RawDocument(
            id=doc_id, person_id=person_id, source_type=SourceType.TELEGRAM,
            url=doc_url, published_at=datetime(2023, 6, 15),
            raw_text="Test prediction text",
        )
    )
    found = await source_repo.get_document_by_url(doc_url)
    assert found is not None

    # Create prediction
    pred_id = str(uuid.uuid4())
    await pred_repo.save(
        Prediction(
            id=pred_id, document_id=doc_id, person_id=person_id,
            claim_text="Test claim", prediction_date=date(2023, 6, 15),
            status=PredictionStatus.UNRESOLVED,
        )
    )
    preds = await pred_repo.get_by_person(person_id)
    assert len(preds) == 1

    # Verify update
    pred = preds[0]
    pred.status = PredictionStatus.CONFIRMED
    pred.confidence = 0.95
    await pred_repo.update(pred)

    updated = await pred_repo.get_by_person(person_id, PredictionStatus.CONFIRMED)
    assert len(updated) == 1
    assert updated[0].confidence == 0.95

    await engine.dispose()
```

- [ ] **Step 2: Run integration test**

```bash
DATABASE_URL=postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker \
pytest tests/test_integration.py -v
```

Expected: 1 test PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration smoke test for full storage round trip"
git push
```

**🏁 End of Task 19. Milestone M4 complete!** STOP. Show summary to user. Wait for explicit approval before M5.

---

## Task 20: GitHub Actions CI 📋 PLANNED

**Files:**
- Create: `prediction-tracker/.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

```yaml
# prediction-tracker/.github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: prophet
          POSTGRES_PASSWORD: prophet
          POSTGRES_DB: prophet_checker_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U prophet"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint
        run: ruff check src/ tests/

      - name: Run unit tests
        run: pytest tests/ -v --ignore=tests/test_integration.py

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql+asyncpg://prophet:prophet@localhost:5432/prophet_checker_test
        run: |
          alembic upgrade head
          pytest tests/test_integration.py -v
```

- [ ] **Step 2: Push and verify CI runs**

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflow with PostgreSQL service"
git push
```

Check GitHub Actions tab — should see green pipeline.

- [ ] **Step 3: Add CI badge to README**

Add to top of `README.md`:
```markdown
![CI](https://github.com/evgeniy44/prediction-tracker/actions/workflows/ci.yml/badge.svg)
```

```bash
git add README.md
git commit -m "docs: add CI badge to README"
git push
```

**🏁 End of Task 20.** STOP. Show summary to user. Wait for explicit approval before Task 21.

---

## Task 21: Source Interface + Telegram Collector 📋 PLANNED

**Files:**
- Create: `prediction-tracker/src/prophet_checker/sources/__init__.py`
- Create: `prediction-tracker/src/prophet_checker/sources/interface.py`
- Create: `prediction-tracker/src/prophet_checker/sources/telegram_collector.py`
- Create: `prediction-tracker/tests/test_sources_telegram.py`

- [ ] **Step 1: Write tests**

```python
# prediction-tracker/tests/test_sources_telegram.py
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from prophet_checker.sources.interface import Source
from prophet_checker.sources.telegram_collector import TelegramCollector
from prophet_checker.models.domain import RawDocument, SourceType


def test_telegram_collector_implements_source():
    collector = TelegramCollector(api_id=1, api_hash="hash", session_name="test")
    assert isinstance(collector, Source)


async def test_telegram_collector_collect():
    collector = TelegramCollector(api_id=1, api_hash="hash", session_name="test")
    mock_message = MagicMock()
    mock_message.id = 123
    mock_message.date = datetime(2023, 6, 15, 10, 30)
    mock_message.text = "Прогноз: контрнаступ буде влітку"
    mock_client = AsyncMock()
    mock_client.get_messages = AsyncMock(return_value=[mock_message])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    with patch.object(collector, "_get_client", return_value=mock_client):
        docs = await collector.collect(
            person_id="p1", channel="@arestovych",
            date_from=date(2023, 1, 1), date_to=date(2023, 12, 31),
        )
    assert len(docs) == 1
    assert docs[0].source_type == SourceType.TELEGRAM
    assert "контрнаступ" in docs[0].raw_text


async def test_telegram_collector_skips_empty_messages():
    collector = TelegramCollector(api_id=1, api_hash="hash", session_name="test")
    msg_with_text = MagicMock()
    msg_with_text.id = 1
    msg_with_text.date = datetime(2023, 1, 1)
    msg_with_text.text = "Valid text"
    msg_without_text = MagicMock()
    msg_without_text.id = 2
    msg_without_text.date = datetime(2023, 1, 2)
    msg_without_text.text = None
    mock_client = AsyncMock()
    mock_client.get_messages = AsyncMock(return_value=[msg_with_text, msg_without_text])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    with patch.object(collector, "_get_client", return_value=mock_client):
        docs = await collector.collect(
            person_id="p1", channel="@chan",
            date_from=date(2023, 1, 1), date_to=date(2023, 12, 31),
        )
    assert len(docs) == 1
```

- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

**🏁 End of Task 21.** STOP. Show summary to user. Wait for explicit approval before Task 22.

---

## Task 22: News Collector 📋 PLANNED

**Files:**
- Create: `prediction-tracker/src/prophet_checker/sources/news_collector.py`
- Create: `prediction-tracker/tests/test_sources_news.py`

- [ ] **Step 1: Write tests**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

**🏁 End of Task 22.** STOP. Show summary to user. Wait for explicit approval before Task 23.

---

## Task 23: AWS RDS PostgreSQL + pgvector 📋 PLANNED

**Files:**
- Create: `prediction-tracker/infra/setup-rds.sh`

- [ ] **Step 1: Install AWS CLI (if not installed)**

```bash
brew install awscli
aws configure
```

- [ ] **Step 2: Create RDS instance with pgvector**

```bash
# prediction-tracker/infra/setup-rds.sh
#!/bin/bash
set -euo pipefail

DB_INSTANCE="prediction-tracker-db"
DB_NAME="prophet_checker"
DB_USER="prophet"
DB_PASS="$(openssl rand -base64 16 | tr -d '=/+')"
REGION="eu-central-1"

echo "Creating RDS instance..."
aws rds create-db-instance \
  --db-instance-identifier "$DB_INSTANCE" \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --engine-version "16.4" \
  --master-username "$DB_USER" \
  --master-user-password "$DB_PASS" \
  --allocated-storage 20 \
  --storage-type gp3 \
  --db-name "$DB_NAME" \
  --publicly-accessible \
  --backup-retention-period 7 \
  --region "$REGION" \
  --no-multi-az

echo "Waiting for instance to become available..."
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE" \
  --region "$REGION"

ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE" \
  --region "$REGION" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

echo ""
echo "=== RDS Ready ==="
echo "Endpoint: $ENDPOINT"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo "Password: $DB_PASS"
echo ""
echo "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@${ENDPOINT}:5432/${DB_NAME}"
```

- [ ] **Step 3: Run setup script**

```bash
chmod +x infra/setup-rds.sh
./infra/setup-rds.sh
```

Save the output DATABASE_URL — you'll need it for EC2.

- [ ] **Step 4: Enable pgvector extension**

```bash
psql "postgresql://prophet:<password>@<endpoint>:5432/prophet_checker" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

- [ ] **Step 5: Run Alembic migration against RDS**

```bash
DATABASE_URL="postgresql+asyncpg://prophet:<password>@<endpoint>:5432/prophet_checker" \
alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add infra/
git commit -m "infra: add RDS setup script for PostgreSQL + pgvector"
git push
```

**🏁 End of Task 23.** STOP. Show summary to user. Wait for explicit approval before Task 24.

---

## Task 24: AWS EC2 + Deploy 📋 PLANNED

**Files:**
- Create: `prediction-tracker/infra/setup-ec2.sh`
- Create: `prediction-tracker/infra/deploy.sh`

- [ ] **Step 1: Create EC2 setup script**

```bash
# prediction-tracker/infra/setup-ec2.sh
#!/bin/bash
set -euo pipefail

INSTANCE_NAME="prediction-tracker"
REGION="eu-central-1"
AMI_ID="ami-0faab6bdbac9486fb"  # Amazon Linux 2023 eu-central-1, update if needed
KEY_NAME="prediction-tracker-key"

echo "Creating key pair..."
aws ec2 create-key-pair \
  --key-name "$KEY_NAME" \
  --query 'KeyMaterial' \
  --output text \
  --region "$REGION" > "${KEY_NAME}.pem"
chmod 400 "${KEY_NAME}.pem"

echo "Creating security group..."
SG_ID=$(aws ec2 create-security-group \
  --group-name "${INSTANCE_NAME}-sg" \
  --description "Security group for prediction-tracker" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)

# Allow SSH
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" --protocol tcp --port 22 --cidr 0.0.0.0/0 --region "$REGION"
# Allow app port
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" --protocol tcp --port 8000 --cidr 0.0.0.0/0 --region "$REGION"

echo "Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t3.micro \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --region "$REGION" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}}]" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Waiting for instance to start..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"

PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo ""
echo "=== EC2 Ready ==="
echo "Instance: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo "SSH: ssh -i ${KEY_NAME}.pem ec2-user@${PUBLIC_IP}"
echo ""
echo "Next: run deploy.sh to install Docker and deploy the app"
```

- [ ] **Step 2: Create deploy script**

```bash
# prediction-tracker/infra/deploy.sh
#!/bin/bash
set -euo pipefail

EC2_HOST="${1:?Usage: deploy.sh <ec2-host>}"
KEY_FILE="${2:-prediction-tracker-key.pem}"

echo "=== Installing Docker on EC2 ==="
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no "ec2-user@${EC2_HOST}" << 'REMOTE'
  sudo dnf update -y
  sudo dnf install -y docker git
  sudo systemctl start docker
  sudo systemctl enable docker
  sudo usermod -aG docker ec2-user

  # Install docker compose plugin
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
REMOTE

echo "=== Cloning repo ==="
ssh -i "$KEY_FILE" "ec2-user@${EC2_HOST}" << 'REMOTE'
  if [ -d prediction-tracker ]; then
    cd prediction-tracker && git pull
  else
    git clone https://github.com/evgeniy44/prediction-tracker.git
    cd prediction-tracker
  fi
REMOTE

echo "=== Uploading .env ==="
scp -i "$KEY_FILE" .env "ec2-user@${EC2_HOST}:~/prediction-tracker/.env"

echo "=== Building and starting ==="
ssh -i "$KEY_FILE" "ec2-user@${EC2_HOST}" << 'REMOTE'
  cd prediction-tracker
  docker compose -f docker-compose.prod.yml up -d --build
REMOTE

echo ""
echo "=== Deployed ==="
echo "App: http://${EC2_HOST}:8000/health"
```

- [ ] **Step 3: Create production docker-compose**

```yaml
# prediction-tracker/docker-compose.prod.yml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
```

Production compose has no local DB — uses RDS via DATABASE_URL in .env.

- [ ] **Step 4: Run EC2 setup**

```bash
chmod +x infra/setup-ec2.sh infra/deploy.sh
./infra/setup-ec2.sh
```

- [ ] **Step 5: Create .env for production and deploy**

```bash
# Create .env with RDS connection string and API keys
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://prophet:<password>@<rds-endpoint>:5432/prophet_checker
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your-key
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_API_ID=your-id
TELEGRAM_API_HASH=your-hash
EOF

./infra/deploy.sh <ec2-public-ip>
```

- [ ] **Step 6: Verify deployment**

```bash
curl http://<ec2-public-ip>:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 7: Commit**

```bash
git add infra/ docker-compose.prod.yml
git commit -m "infra: add EC2 setup and deploy scripts, production compose"
git push
```

**🏁 End of Task 24. Milestone M6 complete! App is live!** STOP. Show final summary to user.

---

## Summary

| Milestone | Task | Description | Tests |
|-----------|------|-------------|-------|
| **M1** | 0 | GitHub repo setup | — |
| | 1 | Project scaffold + config | 2 |
| | 2 | Domain models (Pydantic) | 6 |
| | 3 | Storage interfaces (Protocol) | 7 |
| | 4 | SQLAlchemy ORM + Alembic config | 1 (import check) |
| | 📝 | Post 1: Чому Java TL пише на Python | — |
| **M2** | 5 | PostgreSQL storage implementation | 5 |
| | 6 | LLM client (LiteLLM) | 3 |
| | 7 | Prompt templates | 8 |
| | 8 | Source interface + Telegram collector | 3 |
| | 9 | News collector | 3 |
| | 📝 | Post 2: Prompt engineering для UA тексту | — |
| **M3** | 10 | Prediction extractor | 3 |
| | 11 | Prediction verifier | 4 |
| | 12 | Ingestion pipeline orchestrator | 2 |
| | 📝 | Post 3: AI-верифікація прогнозів | — |
| **M4** | 13 | FastAPI entry point | 1 (import check) |
| | 14 | Docker + Docker Compose | manual |
| | 15 | Alembic migration + integration test | 1 |
| | 📝 | Post 4: Від ідеї до Docker Compose | — |
| **M5** | 16 | GitHub Actions CI | manual |
| | 17 | AWS RDS PostgreSQL + pgvector | manual |
| | 18 | AWS EC2 + deploy | manual |
| | 📝 | Post 5: Деплой на AWS за $25/міс | — |

**Total: 19 tasks, ~49 automated tests, 5 milestones, 6 posts (incl. Post 0)**

**Pace:** One task per session. Push to GitHub after each task. Take breaks between milestones.

**Estimated AWS cost:**
- EC2 t3.micro: free tier (year 1) or ~$8/mo
- RDS db.t4g.micro: ~$12/mo (20GB gp3)
- LLM API: ~$5-20/mo
- **Total: ~$25-40/mo**

After these tasks, the full pipeline is deployed: collect → extract → verify → query via Telegram. The Telegram bot handlers (chat flow with RAG) are deferred per spec — that's the next plan after this foundation is live.
