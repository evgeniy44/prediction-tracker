# IngestionOrchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire existing components (`TelegramSource`, `PredictionExtractor`, `EmbeddingClient`, repos) into a single `IngestionOrchestrator.run_cycle()` що processит всі активні `PersonSource` рядки через single-tier extraction pipeline з cursor-based dedup, atomic per-post transactions, та halt-channel-on-error semantics.

**Architecture:** Single-tier (extract-only) pipeline. Per-post: `extract → if non-empty: embed-each → atomic-tx-save+cursor; else: atomic-tx-cursor`. Cursor — `PersonSource.last_collected_at` (NEW field, NOT NULL `server_default=NOW()`). Per-post atomicity через `async_sessionmaker` factory + `session.begin()`. Repos accept optional `session` param (backward-compat).

**Tech Stack:** Python 3.12, async/await, pytest-asyncio, SQLAlchemy 2.0 async, Alembic, pgvector, Pydantic v2.

**Spec:** [`2026-05-01-ingestion-orchestrator-design.md`](2026-05-01-ingestion-orchestrator-design.md) (revised single-tier)

**Test count delta:** +11 (9 orchestrator unit + 2 integration). 101 → 112.

---

## File Structure (locked-in)

```
src/prophet_checker/
  ingestion/                       NEW package
    __init__.py                    exports IngestionOrchestrator + reports
    orchestrator.py                IngestionOrchestrator class
    report.py                      CycleReport, ChannelReport (Pydantic)

  sources/
    mock.py                        NEW: MockSource for tests

  models/
    domain.py                      MODIFIED: PersonSource.last_collected_at field
    db.py                          MODIFIED: PersonSourceDB.last_collected_at column

  storage/
    interfaces.py                  MODIFIED: SourceRepository + PredictionRepository session-aware
    postgres.py                    MODIFIED: implementations

alembic/versions/
  <rev>_add_last_collected_at_to_person_sources.py    NEW

tests/
  fakes.py                         NEW: shared Fake* repos
  test_storage_interfaces.py       MODIFIED: import from fakes.py
  test_ingestion_orchestrator.py   NEW (9 tests)
  test_ingestion_integration.py    NEW (2 tests)
```

---

## Task 1: Add `last_collected_at` field to `PersonSource` (domain + DB + mappers)

**Files:**
- Modify: `src/prophet_checker/models/domain.py:31-36` (PersonSource class)
- Modify: `src/prophet_checker/models/db.py:37-46` (PersonSourceDB class)
- Modify: `src/prophet_checker/storage/postgres.py:29-40` (mapper functions)
- Modify: `tests/test_models.py` (add new field assertions)

- [ ] **Step 1: Read current state**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
.venv/bin/python -m pytest tests/test_models.py -v 2>&1 | tail -20
```

Note current passing test count for `test_models.py`.

- [ ] **Step 2: Add failing test in `tests/test_models.py`**

Find existing PersonSource test or add at end of file. Append:

```python
from datetime import UTC, datetime


def test_person_source_default_last_collected_at_is_creation_time():
    before = datetime.now(UTC)
    ps = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
    )
    after = datetime.now(UTC)
    assert ps.last_collected_at is not None
    assert before <= ps.last_collected_at <= after


def test_person_source_explicit_last_collected_at_preserved():
    explicit = datetime(2024, 1, 15, tzinfo=UTC)
    ps = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=explicit,
    )
    assert ps.last_collected_at == explicit
```

- [ ] **Step 3: Run new tests, expect failure**

```bash
.venv/bin/python -m pytest tests/test_models.py::test_person_source_default_last_collected_at_is_creation_time tests/test_models.py::test_person_source_explicit_last_collected_at_preserved -v
```

Expected: FAIL — `PersonSource` не має поля `last_collected_at`.

- [ ] **Step 4: Update `PersonSource` domain model**

In `src/prophet_checker/models/domain.py`, find:

```python
class PersonSource(BaseModel):
    id: str
    person_id: str
    source_type: SourceType
    source_identifier: str
    enabled: bool = True
```

Replace with:

```python
class PersonSource(BaseModel):
    id: str
    person_id: str
    source_type: SourceType
    source_identifier: str
    enabled: bool = True
    last_collected_at: datetime | None = None

    def model_post_init(self, __context) -> None:
        if self.last_collected_at is None:
            self.last_collected_at = datetime.now(UTC)
```

- [ ] **Step 5: Run failing tests, verify pass**

```bash
.venv/bin/python -m pytest tests/test_models.py -v
```

Expected: всі (existing + 2 нових) проходять.

- [ ] **Step 6: Update `PersonSourceDB` (SQLAlchemy)**

In `src/prophet_checker/models/db.py`, find:

```python
class PersonSourceDB(Base):
    __tablename__ = "person_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    person: Mapped[PersonDB] = relationship(back_populates="sources")
```

Add `last_collected_at` column after `enabled`:

```python
class PersonSourceDB(Base):
    __tablename__ = "person_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    person: Mapped[PersonDB] = relationship(back_populates="sources")
```

- [ ] **Step 7: Update mapper functions in `storage/postgres.py`**

Find:

```python
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
```

Replace with:

```python
def domain_to_person_source_db(ps: PersonSource) -> PersonSourceDB:
    return PersonSourceDB(
        id=ps.id, person_id=ps.person_id, source_type=ps.source_type.value,
        source_identifier=ps.source_identifier, enabled=ps.enabled,
        last_collected_at=ps.last_collected_at,
    )


def person_source_db_to_domain(db: PersonSourceDB) -> PersonSource:
    return PersonSource(
        id=db.id, person_id=db.person_id, source_type=SourceType(db.source_type),
        source_identifier=db.source_identifier, enabled=db.enabled,
        last_collected_at=db.last_collected_at,
    )
```

- [ ] **Step 8: Run full suite, verify no regression**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 103 passing (101 baseline + 2 new). Якщо `test_storage_postgres.py` падає на нових polovinhah — це OK (Postgres tests часто не запускаються без real DB), main check — `tests/test_models.py` зелений.

- [ ] **Step 9: Commit**

```bash
git add src/prophet_checker/models/domain.py src/prophet_checker/models/db.py src/prophet_checker/storage/postgres.py tests/test_models.py
git commit -m "feat(models): add last_collected_at cursor to PersonSource (Task 15)"
```

---

## Task 2: Alembic migration for `last_collected_at` column

**Files:**
- Create: `alembic/versions/<auto-rev>_add_last_collected_at_to_person_sources.py`

- [ ] **Step 1: Verify Alembic configured**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
ls alembic/ alembic.ini 2>&1 | head -10
```

If Alembic not configured (no `alembic/` directory), this is a real blocker — escalate to user. Else proceed.

- [ ] **Step 2: Generate migration script**

```bash
.venv/bin/alembic revision -m "add last_collected_at to person_sources"
```

Note the generated file path printed (e.g., `alembic/versions/abc123_add_last_collected_at_to_person_sources.py`).

- [ ] **Step 3: Edit migration script**

Open the generated file. Find empty `upgrade()` and `downgrade()` functions. Replace with:

```python
def upgrade() -> None:
    op.add_column(
        "person_sources",
        sa.Column(
            "last_collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("person_sources", "last_collected_at")
```

Imports at top of file should already include `sqlalchemy as sa` and `from alembic import op`.

- [ ] **Step 4: Verify migration script syntax**

```bash
.venv/bin/python -c "
import importlib.util
import pathlib
files = list(pathlib.Path('alembic/versions').glob('*add_last_collected_at*'))
assert len(files) == 1, f'expected 1 migration file, got {files}'
spec = importlib.util.spec_from_file_location('m', files[0])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print('migration loaded OK:', files[0].name)
"
```

Expected: prints `migration loaded OK: <filename>`.

- [ ] **Step 5: Commit migration**

```bash
git add alembic/versions/
git commit -m "feat(alembic): add last_collected_at column migration (Task 15)"
```

---

## Task 3: Extract Fake* repos to `tests/fakes.py` + add new methods

**Files:**
- Modify: `pyproject.toml:46` (add "tests" to pythonpath for cross-test imports)
- Create: `tests/fakes.py`
- Modify: `tests/test_storage_interfaces.py:1-92` (remove Fake* classes, import from fakes)
- Modify: `src/prophet_checker/storage/interfaces.py` (add new Protocol methods)

- [ ] **Step 1: Add `tests` to pythonpath**

In `pyproject.toml`, find:

```toml
pythonpath = ["src", "scripts"]  # src for production code; scripts for eval/smoke scripts under test
```

Replace with:

```toml
pythonpath = ["src", "scripts", "tests"]  # src for production code; scripts for eval/smoke scripts under test; tests for shared fixtures (fakes.py)
```

Verify by running:

```bash
.venv/bin/python -m pytest tests/ -q --collect-only 2>&1 | tail -5
```

Expected: pytest collects without errors.

- [ ] **Step 2: Create `tests/fakes.py` with extracted classes**

Read current `tests/test_storage_interfaces.py` lines 18-92 (Fake* class definitions). Move ALL four Fake classes — `FakePersonRepo`, `FakeSourceRepo`, `FakePredictionRepo`, `FakeVectorStore` — into a new file `tests/fakes.py`. Add imports.

Create `tests/fakes.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from prophet_checker.models.domain import (
    Person,
    PersonSource,
    Prediction,
    PredictionStatus,
    RawDocument,
    SourceType,
)
from prophet_checker.storage.interfaces import (
    PersonRepository,
    PredictionRepository,
    SourceRepository,
    VectorStore,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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

    async def get_person_sources(
        self, person_id: str, source_type: SourceType | None = None
    ) -> list[PersonSource]:
        return [
            s for s in self._sources
            if s.person_id == person_id and (source_type is None or s.source_type == source_type)
        ]

    async def save_document(self, doc: RawDocument) -> RawDocument:
        self._documents.append(doc)
        return doc

    async def get_document_by_url(self, url: str) -> RawDocument | None:
        return next((d for d in self._documents if d.url == url), None)

    async def get_unprocessed_documents(self) -> list[RawDocument]:
        return self._documents

    async def get_last_collected_at(
        self, person_id: str, source_type: SourceType
    ) -> datetime | None:
        docs = [
            d for d in self._documents
            if d.person_id == person_id and d.source_type == source_type
        ]
        if not docs:
            return None
        return max(d.collected_at for d in docs)

    async def list_active_sources(self) -> list[PersonSource]:
        return [s for s in self._sources if s.enabled]

    async def update_source_cursor(
        self,
        person_source_id: str,
        cursor: datetime,
        session: "AsyncSession | None" = None,
    ) -> None:
        for i, s in enumerate(self._sources):
            if s.id == person_source_id:
                self._sources[i] = s.model_copy(update={"last_collected_at": cursor})
                return


class FakePredictionRepo(PredictionRepository):
    def __init__(self):
        self._predictions: list[Prediction] = []

    async def save(
        self,
        prediction: Prediction,
        session: "AsyncSession | None" = None,
    ) -> Prediction:
        self._predictions.append(prediction)
        return prediction

    async def get_by_person(
        self, person_id: str, status: PredictionStatus | None = None
    ) -> list[Prediction]:
        return [
            p for p in self._predictions
            if p.person_id == person_id and (status is None or p.status == status)
        ]

    async def get_unverified(self) -> list[Prediction]:
        return [
            p for p in self._predictions
            if p.status == PredictionStatus.UNRESOLVED and p.verified_at is None
        ]

    async def update(self, prediction: Prediction) -> Prediction:
        self._predictions = [
            p if p.id != prediction.id else prediction
            for p in self._predictions
        ]
        return prediction


class FakeVectorStore(VectorStore):
    def __init__(self):
        self._entries: list[tuple[str, list[float]]] = []

    async def store_embedding(self, prediction_id: str, embedding: list[float]) -> None:
        self._entries.append((prediction_id, embedding))

    async def search_similar(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[str]:
        return [pid for pid, _ in self._entries[:limit]]
```

- [ ] **Step 3: Update `tests/test_storage_interfaces.py` to import from fakes**

Replace lines 1-92 (all imports + 4 Fake* classes) with this top section:

```python
from datetime import date, datetime

from prophet_checker.models.domain import (
    Person,
    PersonSource,
    Prediction,
    PredictionStatus,
    RawDocument,
    SourceType,
)
from fakes import (
    FakePersonRepo,
    FakePredictionRepo,
    FakeSourceRepo,
    FakeVectorStore,
)
```

Lines 95+ (test functions) — leave unchanged.

- [ ] **Step 4: Update Protocol in `storage/interfaces.py`**

Find:

```python
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
```

Add two new methods to the Protocol:

```python
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
    async def list_active_sources(self) -> list[PersonSource]: ...
    async def update_source_cursor(
        self,
        person_source_id: str,
        cursor: datetime,
        session: "AsyncSession | None" = None,
    ) -> None: ...
```

Find:

```python
class PredictionRepository(Protocol):
    async def save(self, prediction: Prediction) -> Prediction: ...
```

Replace with:

```python
class PredictionRepository(Protocol):
    async def save(
        self,
        prediction: Prediction,
        session: "AsyncSession | None" = None,
    ) -> Prediction: ...
```

Add this import at top of `interfaces.py` (under existing imports):

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
```

- [ ] **Step 5: Run all storage tests, verify pass**

```bash
.venv/bin/python -m pytest tests/test_storage_interfaces.py -v
```

Expected: всі тести проходять (FakeSourceRepo + FakePredictionRepo тепер мають нові методи; existing tests все ще pass).

- [ ] **Step 6: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 103 passing (no regressions, no new tests added in this task).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml tests/fakes.py tests/test_storage_interfaces.py src/prophet_checker/storage/interfaces.py
git commit -m "refactor(tests): extract Fake* repos to shared module + add session-aware Protocol methods (Task 15)"
```

---

## Task 4: PostgresSourceRepository — implement `list_active_sources` + `update_source_cursor`

**Files:**
- Modify: `src/prophet_checker/storage/postgres.py:106-156` (PostgresSourceRepository class)
- Modify: `src/prophet_checker/storage/postgres.py:159-199` (PostgresPredictionRepository.save signature)

- [ ] **Step 1: Add `list_active_sources` to PostgresSourceRepository**

In `src/prophet_checker/storage/postgres.py`, find:

```python
class PostgresSourceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save_person_source(self, ps: PersonSource) -> PersonSource:
```

Add method `list_active_sources` after `__init__`:

```python
class PostgresSourceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def list_active_sources(self) -> list[PersonSource]:
        async with self._session_factory() as session:
            stmt = select(PersonSourceDB).where(PersonSourceDB.enabled == True)
            result = await session.execute(stmt)
            return [person_source_db_to_domain(row) for row in result.scalars().all()]

    async def save_person_source(self, ps: PersonSource) -> PersonSource:
```

- [ ] **Step 2: Add `update_source_cursor` to PostgresSourceRepository**

Find existing `get_last_collected_at` method (last in PostgresSourceRepository class). Add new method after it:

```python
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

    async def update_source_cursor(
        self,
        person_source_id: str,
        cursor: datetime,
        session: AsyncSession | None = None,
    ) -> None:
        if session is not None:
            db_obj = await session.get(PersonSourceDB, person_source_id)
            if db_obj is not None:
                db_obj.last_collected_at = cursor
            return
        async with self._session_factory() as own_session:
            db_obj = await own_session.get(PersonSourceDB, person_source_id)
            if db_obj is not None:
                db_obj.last_collected_at = cursor
                await own_session.commit()
```

- [ ] **Step 3: Update PostgresPredictionRepository.save signature**

In `src/prophet_checker/storage/postgres.py`, find:

```python
class PostgresPredictionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(self, prediction: Prediction) -> Prediction:
        async with self._session_factory() as session:
            db_obj = domain_to_prediction_db(prediction)
            session.add(db_obj)
            await session.commit()
            return prediction
```

Replace with:

```python
class PostgresPredictionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(
        self,
        prediction: Prediction,
        session: AsyncSession | None = None,
    ) -> Prediction:
        if session is not None:
            db_obj = domain_to_prediction_db(prediction)
            session.add(db_obj)
            return prediction
        async with self._session_factory() as own_session:
            db_obj = domain_to_prediction_db(prediction)
            own_session.add(db_obj)
            await own_session.commit()
            return prediction
```

- [ ] **Step 4: Run full suite, verify no regression**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 103 passing. `test_storage_postgres.py` тести можуть бути skipped/failed якщо немає реального Postgres — це OK. Main check: `test_storage_interfaces.py` зелений.

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/storage/postgres.py
git commit -m "feat(storage): PostgresSourceRepository.list_active_sources + tx-aware update_source_cursor (Task 15)"
```

---

## Task 5: Create MockSource for testing

**Files:**
- Create: `src/prophet_checker/sources/mock.py`
- Modify: `src/prophet_checker/sources/__init__.py` (export MockSource)

- [ ] **Step 1: Verify existing `sources/__init__.py` is empty**

```bash
cat src/prophet_checker/sources/__init__.py
```

Expected: empty output (file exists but has no content). If file has content — STOP and report; this plan assumes empty file.

- [ ] **Step 2: Create `src/prophet_checker/sources/mock.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import AsyncIterator

from prophet_checker.models.domain import PersonSource, RawDocument


class MockSource:
    def __init__(self, documents: list[RawDocument]):
        self._documents = documents

    async def collect(
        self,
        person_source: PersonSource,
        since: datetime | None = None,
    ) -> AsyncIterator[RawDocument]:
        cutoff = since or datetime.min.replace(tzinfo=UTC)
        for doc in self._documents:
            if doc.person_id == person_source.person_id and doc.published_at > cutoff:
                yield doc
```

- [ ] **Step 3: Write `sources/__init__.py`**

Replace the empty file with:

```python
from prophet_checker.sources.base import Source
from prophet_checker.sources.mock import MockSource
from prophet_checker.sources.telegram import TelegramSource

__all__ = ["MockSource", "Source", "TelegramSource"]
```

- [ ] **Step 4: Verify MockSource conforms to Source Protocol**

```bash
.venv/bin/python -c "
from prophet_checker.sources.base import Source
from prophet_checker.sources.mock import MockSource
m = MockSource([])
assert isinstance(m, Source), 'MockSource must implement Source Protocol'
print('OK: MockSource is Source')
"
```

Expected: prints `OK: MockSource is Source`.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 103 passing (no new tests, just new module).

- [ ] **Step 6: Commit**

```bash
git add src/prophet_checker/sources/mock.py src/prophet_checker/sources/__init__.py
git commit -m "feat(sources): MockSource for ingestion integration tests (Task 15)"
```

---

## Task 6: Create `ingestion/report.py` with CycleReport + ChannelReport

**Files:**
- Create: `src/prophet_checker/ingestion/__init__.py`
- Create: `src/prophet_checker/ingestion/report.py`

- [ ] **Step 1: Create `src/prophet_checker/ingestion/__init__.py` (empty stub)**

```python
from prophet_checker.ingestion.report import CycleReport, ChannelReport

__all__ = ["CycleReport", "ChannelReport"]
```

(IngestionOrchestrator буде доданий в Task 7.)

- [ ] **Step 2: Create `src/prophet_checker/ingestion/report.py`**

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChannelReport(BaseModel):
    person_source_id: str
    posts_seen: int = 0
    posts_with_predictions: int = 0
    predictions_extracted: int = 0
    cursor_advanced_to: datetime | None = None
    error: str | None = None


class CycleReport(BaseModel):
    started_at: datetime
    finished_at: datetime
    channels_processed: list[ChannelReport] = Field(default_factory=list)
```

- [ ] **Step 3: Verify imports**

```bash
.venv/bin/python -c "
from prophet_checker.ingestion import CycleReport, ChannelReport
r = ChannelReport(person_source_id='ps1')
assert r.posts_seen == 0
assert r.error is None
print('OK:', r)
"
```

Expected: prints `OK: person_source_id='ps1' posts_seen=0 ...`.

- [ ] **Step 4: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 103 passing.

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/ingestion/
git commit -m "feat(ingestion): CycleReport + ChannelReport Pydantic models (Task 15)"
```

---

## Task 7: IngestionOrchestrator class — control flow + 9 unit tests

**Files:**
- Create: `src/prophet_checker/ingestion/orchestrator.py`
- Modify: `src/prophet_checker/ingestion/__init__.py` (add IngestionOrchestrator export)
- Create: `tests/test_ingestion_orchestrator.py`

This is the largest task — 9 tests + class. Subdivide into TDD slices.

### Slice 7a: Empty cycle (no active sources)

- [ ] **Step 1: Create `tests/test_ingestion_orchestrator.py` skeleton + first test**

```python
from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from prophet_checker.ingestion import ChannelReport, CycleReport
from prophet_checker.ingestion.orchestrator import IngestionOrchestrator
from prophet_checker.models.domain import (
    PersonSource,
    Prediction,
    PredictionStatus,
    RawDocument,
    SourceType,
)
from prophet_checker.sources.mock import MockSource
from fakes import FakeSourceRepo, FakePredictionRepo


def _stub_session_factory():
    factory = MagicMock(spec=async_sessionmaker)
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=tx_ctx)
    tx_ctx.__aexit__ = AsyncMock(return_value=None)
    session.begin = MagicMock(return_value=tx_ctx)
    factory.return_value = session
    return factory, session


def _make_orchestrator(
    *,
    source_repo=None,
    prediction_repo=None,
    extractor=None,
    embedder=None,
    sources=None,
    session_factory=None,
):
    factory, _session = (session_factory or _stub_session_factory())
    return IngestionOrchestrator(
        session_factory=factory if not isinstance(factory, tuple) else factory[0],
        source_repo=source_repo or FakeSourceRepo(),
        prediction_repo=prediction_repo or FakePredictionRepo(),
        extractor=extractor or _make_extractor([]),
        embedder=embedder or _make_embedder(),
        sources=sources or {},
    )


def _make_extractor(predictions: list[Prediction]):
    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=predictions)
    return extractor


def _make_embedder(vector: list[float] | None = None):
    embedder = MagicMock()
    embedder.embed = AsyncMock(return_value=vector or [0.1] * 1536)
    return embedder


async def test_run_cycle_no_active_sources():
    factory, _ = _stub_session_factory()
    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=FakeSourceRepo(),
        prediction_repo=FakePredictionRepo(),
        extractor=_make_extractor([]),
        embedder=_make_embedder(),
        sources={},
    )

    report = await orchestrator.run_cycle()

    assert isinstance(report, CycleReport)
    assert report.channels_processed == []
```

- [ ] **Step 2: Run, expect import failure**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_run_cycle_no_active_sources -v
```

Expected: ImportError or ModuleNotFoundError на `prophet_checker.ingestion.orchestrator`.

- [ ] **Step 3: Create minimal `src/prophet_checker/ingestion/orchestrator.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Mapping

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from prophet_checker.ingestion.report import ChannelReport, CycleReport
from prophet_checker.models.domain import SourceType
from prophet_checker.sources.base import Source
from prophet_checker.storage.interfaces import (
    PredictionRepository,
    SourceRepository,
)


class IngestionOrchestrator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        source_repo: SourceRepository,
        prediction_repo: PredictionRepository,
        extractor,
        embedder,
        sources: Mapping[SourceType, Source],
    ) -> None:
        self._session_factory = session_factory
        self._source_repo = source_repo
        self._prediction_repo = prediction_repo
        self._extractor = extractor
        self._embedder = embedder
        self._sources = sources

    async def run_cycle(self) -> CycleReport:
        started_at = datetime.now(UTC)
        active = await self._source_repo.list_active_sources()
        channels: list[ChannelReport] = []
        for ps in active:
            report = await self._process_channel(ps)
            channels.append(report)
        finished_at = datetime.now(UTC)
        return CycleReport(
            started_at=started_at,
            finished_at=finished_at,
            channels_processed=channels,
        )

    async def _process_channel(self, ps) -> ChannelReport:
        return ChannelReport(person_source_id=ps.id)
```

- [ ] **Step 4: Update `ingestion/__init__.py`**

Replace:

```python
from prophet_checker.ingestion.report import CycleReport, ChannelReport

__all__ = ["CycleReport", "ChannelReport"]
```

with:

```python
from prophet_checker.ingestion.orchestrator import IngestionOrchestrator
from prophet_checker.ingestion.report import ChannelReport, CycleReport

__all__ = ["ChannelReport", "CycleReport", "IngestionOrchestrator"]
```

- [ ] **Step 5: Run test, verify pass**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_run_cycle_no_active_sources -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/prophet_checker/ingestion/ tests/test_ingestion_orchestrator.py
git commit -m "feat(ingestion): IngestionOrchestrator skeleton + run_cycle empty path (Task 15 slice 7a)"
```

### Slice 7b: Process posts in single channel

- [ ] **Step 1: Add test for happy path**

Append to `tests/test_ingestion_orchestrator.py`:

```python
async def test_run_cycle_processes_posts_in_one_channel():
    person_source = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    docs = [
        RawDocument(
            id=f"tg:arestovich:{i}",
            person_id="p1",
            source_type=SourceType.TELEGRAM,
            url=f"https://t.me/arestovich/{i}",
            published_at=datetime(2024, 1, 2 + i, tzinfo=UTC),
            raw_text=f"Post {i}",
        )
        for i in range(3)
    ]
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    prediction_repo = FakePredictionRepo()
    extractor = MagicMock()
    pred = Prediction(
        id="pred-1",
        document_id="x",
        person_id="p1",
        claim_text="claim",
        prediction_date=date(2024, 1, 1),
    )
    extractor.extract = AsyncMock(side_effect=[[pred], [], [pred, pred]])
    embedder = _make_embedder()
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource(docs)},
    )

    report = await orchestrator.run_cycle()

    assert len(report.channels_processed) == 1
    ch = report.channels_processed[0]
    assert ch.person_source_id == "ps1"
    assert ch.posts_seen == 3
    assert ch.posts_with_predictions == 2
    assert ch.predictions_extracted == 3
    assert extractor.extract.call_count == 3
    assert embedder.embed.call_count == 3
    assert len(prediction_repo._predictions) == 3
```

- [ ] **Step 2: Run, expect failure**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_run_cycle_processes_posts_in_one_channel -v
```

Expected: FAIL — `_process_channel` returns empty ChannelReport, no actual processing.

- [ ] **Step 3: Implement `_process_channel`**

In `src/prophet_checker/ingestion/orchestrator.py`, replace the stub `_process_channel`:

```python
    async def _process_channel(self, ps) -> ChannelReport:
        return ChannelReport(person_source_id=ps.id)
```

with the full implementation:

```python
    async def _process_channel(self, ps) -> ChannelReport:
        report = ChannelReport(
            person_source_id=ps.id,
            cursor_advanced_to=ps.last_collected_at,
        )
        source = self._sources.get(ps.source_type)
        if source is None:
            report.error = f"no source registered for type={ps.source_type.value}"
            return report

        try:
            async for raw_doc in source.collect(ps, since=ps.last_collected_at):
                report.posts_seen += 1
                predictions = await self._extractor.extract(
                    text=raw_doc.raw_text,
                    person_id=raw_doc.person_id,
                    document_id=raw_doc.id,
                    person_name=ps.source_identifier,
                    published_date=raw_doc.published_at.date().isoformat(),
                )
                if predictions:
                    report.posts_with_predictions += 1
                    for p in predictions:
                        p.embedding = await self._embedder.embed(p.claim_text)
                    async with self._session_factory() as session:
                        async with session.begin():
                            for p in predictions:
                                await self._prediction_repo.save(p, session=session)
                            await self._source_repo.update_source_cursor(
                                ps.id, raw_doc.published_at, session=session
                            )
                    report.predictions_extracted += len(predictions)
                else:
                    async with self._session_factory() as session:
                        async with session.begin():
                            await self._source_repo.update_source_cursor(
                                ps.id, raw_doc.published_at, session=session
                            )
                report.cursor_advanced_to = raw_doc.published_at
        except Exception as exc:
            report.error = f"halted at step=processing: {exc}"
        return report
```

- [ ] **Step 4: Run failing test, verify pass**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py -v
```

Expected: both tests pass (test_run_cycle_no_active_sources still passes + test_run_cycle_processes_posts_in_one_channel new pass).

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/ingestion/orchestrator.py tests/test_ingestion_orchestrator.py
git commit -m "feat(ingestion): per-channel processing with extract→embed→save (Task 15 slice 7b)"
```

### Slice 7c: Empty predictions advances cursor without save

- [ ] **Step 1: Add test**

Append:

```python
async def test_empty_predictions_advances_cursor_without_save():
    person_source = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    doc = RawDocument(
        id="tg:arestovich:1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        url="https://t.me/arestovich/1",
        published_at=datetime(2024, 1, 5, tzinfo=UTC),
        raw_text="No predictions here",
    )
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    prediction_repo = FakePredictionRepo()
    extractor = _make_extractor([])
    embedder = _make_embedder()
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource([doc])},
    )

    report = await orchestrator.run_cycle()

    ch = report.channels_processed[0]
    assert ch.posts_seen == 1
    assert ch.posts_with_predictions == 0
    assert ch.predictions_extracted == 0
    assert len(prediction_repo._predictions) == 0
    assert embedder.embed.call_count == 0
    updated = await source_repo.get_person_sources("p1")
    assert updated[0].last_collected_at == datetime(2024, 1, 5, tzinfo=UTC)
```

- [ ] **Step 2: Run, verify pass (already implemented in slice 7b)**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_empty_predictions_advances_cursor_without_save -v
```

Expected: PASS (logic already in place from previous slice).

- [ ] **Step 3: Commit**

```bash
git add tests/test_ingestion_orchestrator.py
git commit -m "test(ingestion): empty predictions advances cursor without save (Task 15 slice 7c)"
```

### Slice 7d: Halt-on-embed-error

- [ ] **Step 1: Add test**

Append:

```python
async def test_embed_failure_halts_channel_no_save():
    person_source = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    doc = RawDocument(
        id="tg:arestovich:1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        url="https://t.me/arestovich/1",
        published_at=datetime(2024, 1, 5, tzinfo=UTC),
        raw_text="Has predictions",
    )
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    prediction_repo = FakePredictionRepo()
    pred = Prediction(
        id="pred-1",
        document_id="x",
        person_id="p1",
        claim_text="claim",
        prediction_date=date(2024, 1, 1),
    )
    extractor = _make_extractor([pred])
    embedder = MagicMock()
    embedder.embed = AsyncMock(side_effect=RuntimeError("embed API down"))
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource([doc])},
    )

    report = await orchestrator.run_cycle()

    ch = report.channels_processed[0]
    assert ch.error is not None
    assert "embed" in ch.error.lower() or "down" in ch.error.lower()
    assert len(prediction_repo._predictions) == 0
    updated = await source_repo.get_person_sources("p1")
    assert updated[0].last_collected_at == datetime(2024, 1, 1, tzinfo=UTC)
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_embed_failure_halts_channel_no_save -v
```

Expected: PASS — try/except catches RuntimeError, sets `error` field, no save called (embed raised before save loop).

- [ ] **Step 3: Commit**

```bash
git add tests/test_ingestion_orchestrator.py
git commit -m "test(ingestion): embed failure halts channel without save (Task 15 slice 7d)"
```

### Slice 7e: Halt-on-save-error rolls back

- [ ] **Step 1: Add test**

Append:

```python
async def test_save_failure_halts_channel():
    person_source = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    doc = RawDocument(
        id="tg:arestovich:1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        url="https://t.me/arestovich/1",
        published_at=datetime(2024, 1, 5, tzinfo=UTC),
        raw_text="Has predictions",
    )
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    prediction_repo = FakePredictionRepo()
    prediction_repo.save = AsyncMock(side_effect=RuntimeError("DB unavailable"))
    pred = Prediction(
        id="pred-1",
        document_id="x",
        person_id="p1",
        claim_text="claim",
        prediction_date=date(2024, 1, 1),
    )
    extractor = _make_extractor([pred])
    embedder = _make_embedder()
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource([doc])},
    )

    report = await orchestrator.run_cycle()

    ch = report.channels_processed[0]
    assert ch.error is not None
    updated = await source_repo.get_person_sources("p1")
    assert updated[0].last_collected_at == datetime(2024, 1, 1, tzinfo=UTC)
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_save_failure_halts_channel -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ingestion_orchestrator.py
git commit -m "test(ingestion): save failure halts channel (Task 15 slice 7e)"
```

### Slice 7f: One channel halt does not block others

- [ ] **Step 1: Add test**

Append:

```python
async def test_one_channel_halt_does_not_block_others():
    ps1 = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    ps2 = PersonSource(
        id="ps2",
        person_id="p2",
        source_type=SourceType.TELEGRAM,
        source_identifier="@podolyak",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    docs = [
        RawDocument(
            id="tg:arestovich:1",
            person_id="p1",
            source_type=SourceType.TELEGRAM,
            url="https://t.me/arestovich/1",
            published_at=datetime(2024, 1, 5, tzinfo=UTC),
            raw_text="Bad post",
        ),
        RawDocument(
            id="tg:podolyak:1",
            person_id="p2",
            source_type=SourceType.TELEGRAM,
            url="https://t.me/podolyak/1",
            published_at=datetime(2024, 1, 5, tzinfo=UTC),
            raw_text="Good post",
        ),
    ]
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(ps1)
    await source_repo.save_person_source(ps2)
    prediction_repo = FakePredictionRepo()

    pred = Prediction(
        id="pred-1",
        document_id="x",
        person_id="p2",
        claim_text="claim",
        prediction_date=date(2024, 1, 1),
    )
    extractor = MagicMock()
    extractor.extract = AsyncMock(side_effect=[RuntimeError("LLM down"), [pred]])
    embedder = _make_embedder()
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource(docs)},
    )

    report = await orchestrator.run_cycle()

    assert len(report.channels_processed) == 2
    by_id = {c.person_source_id: c for c in report.channels_processed}
    assert by_id["ps1"].error is not None
    assert by_id["ps2"].error is None
    assert by_id["ps2"].predictions_extracted == 1
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_one_channel_halt_does_not_block_others -v
```

Expected: PASS — try/except is per-channel.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ingestion_orchestrator.py
git commit -m "test(ingestion): one channel halt does not block others (Task 15 slice 7f)"
```

### Slice 7g: Cursor advances per-post

- [ ] **Step 1: Add test**

Append:

```python
async def test_cursor_advances_per_post():
    person_source = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    docs = [
        RawDocument(
            id=f"tg:arestovich:{i}",
            person_id="p1",
            source_type=SourceType.TELEGRAM,
            url=f"https://t.me/arestovich/{i}",
            published_at=datetime(2024, 1, 2 + i, tzinfo=UTC),
            raw_text=f"Post {i}",
        )
        for i in range(3)
    ]
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    cursor_calls = []
    original_update = source_repo.update_source_cursor

    async def tracking_update(person_source_id, cursor, session=None):
        cursor_calls.append((person_source_id, cursor))
        return await original_update(person_source_id, cursor, session=session)

    source_repo.update_source_cursor = tracking_update

    extractor = _make_extractor([])
    embedder = _make_embedder()
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=source_repo,
        prediction_repo=FakePredictionRepo(),
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource(docs)},
    )

    await orchestrator.run_cycle()

    assert len(cursor_calls) == 3
    assert cursor_calls[0] == ("ps1", datetime(2024, 1, 2, tzinfo=UTC))
    assert cursor_calls[1] == ("ps1", datetime(2024, 1, 3, tzinfo=UTC))
    assert cursor_calls[2] == ("ps1", datetime(2024, 1, 4, tzinfo=UTC))
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_cursor_advances_per_post -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ingestion_orchestrator.py
git commit -m "test(ingestion): cursor advances per-post with each published_at (Task 15 slice 7g)"
```

### Slice 7h: CycleReport aggregates counts + missing source type guard

- [ ] **Step 1: Add tests**

Append:

```python
async def test_cycle_report_aggregates_counts():
    person_source = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    docs = [
        RawDocument(
            id=f"tg:arestovich:{i}",
            person_id="p1",
            source_type=SourceType.TELEGRAM,
            url=f"https://t.me/arestovich/{i}",
            published_at=datetime(2024, 1, 2 + i, tzinfo=UTC),
            raw_text=f"Post {i}",
        )
        for i in range(3)
    ]
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    prediction_repo = FakePredictionRepo()
    pred = Prediction(
        id="pred-1",
        document_id="x",
        person_id="p1",
        claim_text="claim",
        prediction_date=date(2024, 1, 1),
    )
    extractor = MagicMock()
    extractor.extract = AsyncMock(side_effect=[[pred, pred], [], [pred]])
    embedder = _make_embedder()
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource(docs)},
    )

    report = await orchestrator.run_cycle()

    ch = report.channels_processed[0]
    assert ch.posts_seen == 3
    assert ch.posts_with_predictions == 2
    assert ch.predictions_extracted == 3
    assert report.started_at <= report.finished_at


async def test_unregistered_source_type_marks_error_and_continues():
    ps_news = PersonSource(
        id="ps_news",
        person_id="p1",
        source_type=SourceType.NEWS,
        source_identifier="some-news-feed",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(ps_news)
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=source_repo,
        prediction_repo=FakePredictionRepo(),
        extractor=_make_extractor([]),
        embedder=_make_embedder(),
        sources={SourceType.TELEGRAM: MockSource([])},
    )

    report = await orchestrator.run_cycle()

    assert len(report.channels_processed) == 1
    ch = report.channels_processed[0]
    assert ch.error is not None
    assert "NEWS" in ch.error.upper() or "news" in ch.error
```

- [ ] **Step 2: Run, verify both pass**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py -v
```

Expected: всі 8 orchestrator-тестів проходять.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ingestion_orchestrator.py
git commit -m "test(ingestion): cycle report aggregates + missing source type guard (Task 15 slice 7h)"
```

### Slice 7i: Final orchestrator test count check

- [ ] **Step 1: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 112 passing (101 baseline + 2 from Task 1 model tests + 9 orchestrator unit tests = 112). Якщо число не співпадає — investigate before proceeding.

- [ ] **Step 2: Run only ingestion tests for clarity**

```bash
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py -v
```

Expected: 9 tests pass (1 + 1 + 1 + 1 + 1 + 1 + 1 + 2 = 9 across slices 7a–7h).

---

## Task 8: Integration smoke tests

**Files:**
- Create: `tests/test_ingestion_integration.py`

- [ ] **Step 1: Create integration test file**

```python
from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from prophet_checker.ingestion import IngestionOrchestrator
from prophet_checker.models.domain import (
    PersonSource,
    Prediction,
    PredictionStatus,
    RawDocument,
    SourceType,
)
from prophet_checker.sources.mock import MockSource
from fakes import FakeSourceRepo, FakePredictionRepo


def _stub_session_factory():
    factory = MagicMock(spec=async_sessionmaker)
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=tx_ctx)
    tx_ctx.__aexit__ = AsyncMock(return_value=None)
    session.begin = MagicMock(return_value=tx_ctx)
    factory.return_value = session
    return factory


async def test_end_to_end_three_posts_with_mocked_llm():
    person_source = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    docs = [
        RawDocument(
            id=f"tg:arestovich:{i}",
            person_id="p1",
            source_type=SourceType.TELEGRAM,
            url=f"https://t.me/arestovich/{i}",
            published_at=datetime(2024, 1, 2 + i, tzinfo=UTC),
            raw_text=f"Post {i}",
        )
        for i in range(3)
    ]
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    prediction_repo = FakePredictionRepo()

    p1 = Prediction(
        id="pred-a", document_id="x", person_id="p1",
        claim_text="A", prediction_date=date(2024, 1, 1),
    )
    p2 = Prediction(
        id="pred-b", document_id="x", person_id="p1",
        claim_text="B", prediction_date=date(2024, 1, 1),
    )
    p3 = Prediction(
        id="pred-c", document_id="x", person_id="p1",
        claim_text="C", prediction_date=date(2024, 1, 1),
    )

    extractor = MagicMock()
    extractor.extract = AsyncMock(side_effect=[[p1, p2], [], [p3]])
    embedder = MagicMock()
    embedder.embed = AsyncMock(return_value=[0.1] * 1536)

    orchestrator = IngestionOrchestrator(
        session_factory=_stub_session_factory(),
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource(docs)},
    )

    report = await orchestrator.run_cycle()

    ch = report.channels_processed[0]
    assert ch.posts_seen == 3
    assert ch.predictions_extracted == 3
    assert len(prediction_repo._predictions) == 3
    saved_ids = {p.id for p in prediction_repo._predictions}
    assert saved_ids == {"pred-a", "pred-b", "pred-c"}
    updated = await source_repo.get_person_sources("p1")
    assert updated[0].last_collected_at == datetime(2024, 1, 4, tzinfo=UTC)


async def test_halt_recovery_resumes_from_last_cursor():
    person_source = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    docs = [
        RawDocument(
            id=f"tg:arestovich:{i}",
            person_id="p1",
            source_type=SourceType.TELEGRAM,
            url=f"https://t.me/arestovich/{i}",
            published_at=datetime(2024, 1, 2 + i, tzinfo=UTC),
            raw_text=f"Post {i}",
        )
        for i in range(3)
    ]
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    prediction_repo = FakePredictionRepo()

    pred = Prediction(
        id="pred-x", document_id="x", person_id="p1",
        claim_text="X", prediction_date=date(2024, 1, 1),
    )

    cycle1_extract = MagicMock()
    cycle1_extract.extract = AsyncMock(side_effect=[[pred], RuntimeError("LLM down")])
    embedder = MagicMock()
    embedder.embed = AsyncMock(return_value=[0.1] * 1536)

    orch1 = IngestionOrchestrator(
        session_factory=_stub_session_factory(),
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=cycle1_extract,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource(docs)},
    )
    report1 = await orch1.run_cycle()
    assert report1.channels_processed[0].error is not None
    assert len(prediction_repo._predictions) == 1

    updated = await source_repo.get_person_sources("p1")
    assert updated[0].last_collected_at == datetime(2024, 1, 2, tzinfo=UTC)

    cycle2_extract = MagicMock()
    cycle2_extract.extract = AsyncMock(side_effect=[[pred], [pred]])

    orch2 = IngestionOrchestrator(
        session_factory=_stub_session_factory(),
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=cycle2_extract,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource(docs)},
    )
    report2 = await orch2.run_cycle()
    ch2 = report2.channels_processed[0]
    assert ch2.error is None
    assert ch2.posts_seen == 2
    assert ch2.predictions_extracted == 2
    assert len(prediction_repo._predictions) == 3
    final = await source_repo.get_person_sources("p1")
    assert final[0].last_collected_at == datetime(2024, 1, 4, tzinfo=UTC)
```

- [ ] **Step 2: Run integration tests, verify pass**

```bash
.venv/bin/python -m pytest tests/test_ingestion_integration.py -v
```

Expected: 2 tests pass.

- [ ] **Step 3: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 114 passing (101 baseline + 2 model + 9 orchestrator + 2 integration = 114. If different — investigate why before commit).

- [ ] **Step 4: Commit**

```bash
git add tests/test_ingestion_integration.py
git commit -m "test(ingestion): end-to-end + halt-recovery integration smoke (Task 15)"
```

---

## Final verification

- [ ] **Step 1: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 114 tests passing. Specifically:
- 101 baseline (pre-Task 15)
- +2 from `tests/test_models.py` (Task 1: PersonSource.last_collected_at)
- +9 from `tests/test_ingestion_orchestrator.py` (Task 7 slices 7a-7h)
- +2 from `tests/test_ingestion_integration.py` (Task 8)
- **Net: 114 passing**

Note: spec said `+11 tests` (9 orchestrator + 2 integration). Plan delivers 9+2 + 2 model = 13 net new = 114 total. Spec did not count Task 1's model-field tests separately. If number differs significantly (>2 from 114) — investigate.

- [ ] **Step 2: Verify imports work**

```bash
.venv/bin/python -c "
from prophet_checker.ingestion import IngestionOrchestrator, CycleReport, ChannelReport
from prophet_checker.sources.mock import MockSource
print('OK:', IngestionOrchestrator, MockSource)
"
```

Expected: `OK: <class ...IngestionOrchestrator> <class ...MockSource>`.

- [ ] **Step 3: Verify Source Protocol implementation**

```bash
.venv/bin/python -c "
from prophet_checker.sources.base import Source
from prophet_checker.sources.mock import MockSource
from prophet_checker.sources.telegram import TelegramSource
m = MockSource([])
assert isinstance(m, Source), 'MockSource should be Source'
print('OK: MockSource is Source Protocol')
"
```

Expected: `OK: MockSource is Source Protocol`.

- [ ] **Step 4: Verify migration file exists**

```bash
ls alembic/versions/*last_collected_at*
```

Expected: один файл.

- [ ] **Step 5: Verify `enabled` flag filtering**

```bash
.venv/bin/python -c "
import asyncio
from datetime import UTC, datetime
from prophet_checker.models.domain import PersonSource, SourceType
from tests.fakes import FakeSourceRepo

async def main():
    repo = FakeSourceRepo()
    await repo.save_person_source(PersonSource(
        id='enabled1', person_id='p1', source_type=SourceType.TELEGRAM,
        source_identifier='@a', enabled=True,
    ))
    await repo.save_person_source(PersonSource(
        id='disabled1', person_id='p2', source_type=SourceType.TELEGRAM,
        source_identifier='@b', enabled=False,
    ))
    active = await repo.list_active_sources()
    assert len(active) == 1, f'expected 1 active, got {len(active)}'
    assert active[0].id == 'enabled1'
    print('OK: list_active_sources filters by enabled')

asyncio.run(main())
"
```

Expected: `OK: list_active_sources filters by enabled`.

---

## Out of Scope (deferred)

- ❌ Real Postgres + pgvector smoke — Task 19
- ❌ Real Telegram + Gemini integration — Task 19
- ❌ FastAPI HTTP-trigger endpoint (`POST /ingest/run`) — Task 16
- ❌ Concurrent `run_cycle()` protection (mutex/queue) — Task 16
- ❌ Detection prefilter (separate cheap LLM-call) — future task after we see real cost data
- ❌ Two-tier extraction (Flash Lite + Pro Preview) — needs proof-of-concept
- ❌ `extractor.extract()` raise-on-error refactor — deferred (current swallow behavior maintained for eval-script compatibility)
- ❌ Per-post failure count + dead-letter — deferred

---

## Cross-references

- **Spec:** [`2026-05-01-ingestion-orchestrator-design.md`](2026-05-01-ingestion-orchestrator-design.md)
- **Architecture:** [`../architecture/2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md)
- **Source Protocol (Task 21):** `src/prophet_checker/sources/base.py`
- **LLM Client Split (prerequisite):** [`2026-05-01-llm-client-split-design.md`](2026-05-01-llm-client-split-design.md)
