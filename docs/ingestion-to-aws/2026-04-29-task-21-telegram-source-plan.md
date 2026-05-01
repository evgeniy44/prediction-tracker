# Task 21 — Telegram Source Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Telegram collection logic from `scripts/collect_telegram_posts.py` into `src/prophet_checker/sources/telegram.py` with a reusable `Source` Protocol, replacing JSON output with `AsyncIterator[RawDocument]` yielded to orchestrator (Task 15 future).

**Architecture:** Strategy + Async Iterator. `Source` Protocol describes contract; `TelegramSource` is concrete impl. Persistence stays out of `Source` — caller (orchestrator) writes yielded docs through `SourceRepository`.

**Tech Stack:** Python 3.11+, Telethon (existing dep), pytest-asyncio, pydantic 2.

**Spec:** [`2026-04-29-task-21-telegram-source-design.md`](2026-04-29-task-21-telegram-source-design.md)

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `src/prophet_checker/sources/__init__.py` | Create | Package marker |
| `src/prophet_checker/sources/base.py` | Create | `Source` Protocol definition |
| `src/prophet_checker/sources/telegram.py` | Create | `TelegramSource` implementation |
| `tests/sources/__init__.py` | Create | Test package marker |
| `tests/sources/test_telegram.py` | Create | All TelegramSource unit tests |
| `scripts/collect_telegram_posts.py` | Delete | Replaced by src/sources/telegram.py |

---

## Task 1: Source Protocol + package skeleton

**Files:**
- Create: `src/prophet_checker/sources/__init__.py`
- Create: `src/prophet_checker/sources/base.py`
- Test: integration into existing `tests/test_storage_interfaces.py` (just import check — Protocol without runtime methods can't be tested with traditional unit tests)

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p src/prophet_checker/sources tests/sources
touch src/prophet_checker/sources/__init__.py
touch tests/sources/__init__.py
```

- [ ] **Step 2: Write failing test that imports `Source` Protocol**

Add to a NEW file `tests/sources/test_protocol.py`:

```python
from datetime import datetime
from typing import AsyncIterator

from prophet_checker.models.domain import PersonSource, RawDocument
from prophet_checker.sources.base import Source


def test_source_protocol_importable():
    assert Source is not None


def test_source_protocol_has_collect_method():
    assert hasattr(Source, "collect")


class _ConformantImpl:
    async def collect(
        self,
        person_source: PersonSource,
        since: datetime | None = None,
    ) -> AsyncIterator[RawDocument]:
        if False:
            yield


def test_source_protocol_structural_check():
    impl: Source = _ConformantImpl()
    assert impl is not None
```

- [ ] **Step 3: Run test, verify it fails with ImportError**

```bash
.venv/bin/python -m pytest tests/sources/test_protocol.py -v
```

Expected: 3 errors — `ModuleNotFoundError: No module named 'prophet_checker.sources.base'`.

- [ ] **Step 4: Implement `Source` Protocol in `src/prophet_checker/sources/base.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator, Protocol

from prophet_checker.models.domain import PersonSource, RawDocument


class Source(Protocol):
    async def collect(
        self,
        person_source: PersonSource,
        since: datetime | None = None,
    ) -> AsyncIterator[RawDocument]:
        ...
```

- [ ] **Step 5: Run test, verify all 3 pass**

```bash
.venv/bin/python -m pytest tests/sources/test_protocol.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/prophet_checker/sources/ tests/sources/
git commit -m "feat(sources): add Source Protocol package (Task 21)"
```

---

## Task 2: TelegramSource — happy path with filtering

**Files:**
- Create: `src/prophet_checker/sources/telegram.py`
- Create: `tests/sources/test_telegram.py`

- [ ] **Step 1: Add test fixtures + failing happy path test**

Create `tests/sources/test_telegram.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from prophet_checker.models.domain import PersonSource, SourceType
from prophet_checker.sources.telegram import TelegramSource


def make_message(msg_id: int, text: str | None, date: datetime):
    m = MagicMock()
    m.id = msg_id
    m.text = text
    m.date = date
    return m


def make_mock_client(messages, get_entity_raises=None):
    client = MagicMock()
    if get_entity_raises is not None:
        client.get_entity = AsyncMock(side_effect=get_entity_raises("test"))
    else:
        client.get_entity = AsyncMock(return_value=MagicMock())

    async def iter_messages_gen(entity):
        for m in messages:
            yield m

    client.iter_messages = iter_messages_gen
    return client


def make_person_source(
    channel: str = "O_Arestovich_official",
    source_type: SourceType = SourceType.TELEGRAM,
) -> PersonSource:
    return PersonSource(
        id="ps_test",
        person_id="person_test",
        source_type=source_type,
        source_identifier=channel,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_collect_yields_filtered_documents():
    long_text = "А" * 100
    short_text = "shrt"
    msgs = [
        make_message(1, long_text, datetime(2024, 6, 1, tzinfo=UTC)),
        make_message(2, short_text, datetime(2024, 6, 2, tzinfo=UTC)),
        make_message(3, None, datetime(2024, 6, 3, tzinfo=UTC)),
    ]
    client = make_mock_client(msgs)
    source = TelegramSource(client)

    yielded = []
    async for doc in source.collect(make_person_source()):
        yielded.append(doc)

    assert len(yielded) == 1
    assert yielded[0].raw_text == long_text
    assert yielded[0].source_type == SourceType.TELEGRAM
    assert yielded[0].person_id == "person_test"
    assert yielded[0].language == "uk"


@pytest.mark.asyncio
async def test_collect_builds_telegram_url():
    long_text = "А" * 100
    msgs = [make_message(42, long_text, datetime(2024, 6, 1, tzinfo=UTC))]
    client = make_mock_client(msgs)
    source = TelegramSource(client)
    ps = make_person_source(channel="O_Arestovich_official")

    yielded = []
    async for doc in source.collect(ps):
        yielded.append(doc)

    assert yielded[0].url == "https://t.me/O_Arestovich_official/42"


@pytest.mark.asyncio
async def test_collect_preserves_published_at():
    long_text = "А" * 100
    msg_date = datetime(2024, 7, 15, 12, 30, tzinfo=UTC)
    msgs = [make_message(1, long_text, msg_date)]
    client = make_mock_client(msgs)
    source = TelegramSource(client)

    yielded = []
    async for doc in source.collect(make_person_source()):
        yielded.append(doc)

    assert yielded[0].published_at == msg_date
```

- [ ] **Step 2: Run tests, verify ImportError on TelegramSource**

```bash
.venv/bin/python -m pytest tests/sources/test_telegram.py -v
```

Expected: 3 errors — `ModuleNotFoundError`.

- [ ] **Step 3: Implement minimal TelegramSource**

Create `src/prophet_checker/sources/telegram.py`:

```python
from __future__ import annotations

import logging
from datetime import datetime
from typing import AsyncIterator

from telethon import TelegramClient

from prophet_checker.models.domain import (
    PersonSource, RawDocument, SourceType,
)

logger = logging.getLogger(__name__)


class TelegramSource:
    DEFAULT_MIN_TEXT_LENGTH = 80

    def __init__(
        self,
        client: TelegramClient,
        min_text_length: int = DEFAULT_MIN_TEXT_LENGTH,
    ) -> None:
        self._client = client
        self._min_text_length = min_text_length

    async def collect(
        self,
        person_source: PersonSource,
        since: datetime | None = None,
    ) -> AsyncIterator[RawDocument]:
        if person_source.source_type != SourceType.TELEGRAM:
            return

        channel = person_source.source_identifier
        entity = await self._client.get_entity(channel)

        async for msg in self._client.iter_messages(entity):
            if not msg.text or len(msg.text.strip()) < self._min_text_length:
                continue

            yield RawDocument(
                id=f"tg:{channel}:{msg.id}",
                person_id=person_source.person_id,
                source_type=SourceType.TELEGRAM,
                url=f"https://t.me/{channel}/{msg.id}",
                published_at=msg.date,
                raw_text=msg.text.strip(),
            )
```

- [ ] **Step 4: Run tests, verify 3 pass**

```bash
.venv/bin/python -m pytest tests/sources/test_telegram.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/sources/telegram.py tests/sources/test_telegram.py
git commit -m "feat(sources): TelegramSource happy path with text-length filter (Task 21)"
```

---

## Task 3: TelegramSource — `since` filter

**Files:**
- Modify: `tests/sources/test_telegram.py`
- Modify: `src/prophet_checker/sources/telegram.py`

- [ ] **Step 1: Add failing test for `since` cutoff**

Append to `tests/sources/test_telegram.py`:

```python
@pytest.mark.asyncio
async def test_collect_respects_since_param():
    long_text = "А" * 100
    msgs = [
        make_message(3, long_text, datetime(2024, 8, 1, tzinfo=UTC)),
        make_message(2, long_text, datetime(2024, 7, 1, tzinfo=UTC)),
        make_message(1, long_text, datetime(2024, 5, 1, tzinfo=UTC)),
    ]
    client = make_mock_client(msgs)
    source = TelegramSource(client)
    since = datetime(2024, 6, 1, tzinfo=UTC)

    yielded = []
    async for doc in source.collect(make_person_source(), since=since):
        yielded.append(doc)

    assert len(yielded) == 2
    assert yielded[0].published_at == datetime(2024, 8, 1, tzinfo=UTC)
    assert yielded[1].published_at == datetime(2024, 7, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_collect_since_none_yields_all():
    long_text = "А" * 100
    msgs = [
        make_message(2, long_text, datetime(2024, 8, 1, tzinfo=UTC)),
        make_message(1, long_text, datetime(2020, 1, 1, tzinfo=UTC)),
    ]
    client = make_mock_client(msgs)
    source = TelegramSource(client)

    yielded = []
    async for doc in source.collect(make_person_source(), since=None):
        yielded.append(doc)

    assert len(yielded) == 2
```

- [ ] **Step 2: Run tests, verify both new tests fail**

```bash
.venv/bin/python -m pytest tests/sources/test_telegram.py -v
```

Expected: `test_collect_respects_since_param` fails (yields all 3); `test_collect_since_none_yields_all` may pass.

- [ ] **Step 3: Update `collect()` to honor `since`**

In `src/prophet_checker/sources/telegram.py`, modify the `async for msg` loop:

```python
        async for msg in self._client.iter_messages(entity):
            if since is not None and msg.date < since:
                break

            if not msg.text or len(msg.text.strip()) < self._min_text_length:
                continue

            yield RawDocument(
                id=str(uuid4()),
                person_id=person_source.person_id,
                source_type=SourceType.TELEGRAM,
                url=f"https://t.me/{channel}/{msg.id}",
                published_at=msg.date,
                raw_text=msg.text.strip(),
                language="uk",
            )
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
.venv/bin/python -m pytest tests/sources/test_telegram.py -v
```

Expected: 5 passed (3 prior + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/sources/telegram.py tests/sources/test_telegram.py
git commit -m "feat(sources): TelegramSource respects 'since' cutoff for incremental collection (Task 21)"
```

---

## Task 4: TelegramSource — non-Telegram structural skip + propagate channel errors

**Files:**
- Modify: `tests/sources/test_telegram.py`

**Принцип:** Source НЕ catch'ить помилки `get_entity()`. Винятки propagate'яться вгору, orchestrator (Task 15) їх класифікує і вирішує політику. Виняток — `source_type != TELEGRAM`: це structural skip, не error.

- [ ] **Step 1: Add failing tests for structural skip + propagate**

Note: This step also extends `make_mock_client` to accept `get_entity_raises` parameter within this task's test code (see updated helper below). Task 2 removed the parameter for strict YAGNI; Task 4 re-introduces it locally.

First, update the `make_mock_client` helper to restore the `get_entity_raises` parameter:

```python
def make_mock_client(messages, get_entity_raises=None):
    client = MagicMock()
    if get_entity_raises is not None:
        client.get_entity = AsyncMock(side_effect=get_entity_raises("test"))
    else:
        client.get_entity = AsyncMock(return_value=MagicMock())

    async def iter_messages_gen(entity):
        for m in messages:
            yield m

    client.iter_messages = iter_messages_gen
    return client
```

Then append the new tests to `tests/sources/test_telegram.py`:

```python
from telethon.errors import (
    ChannelInvalidError,
    ChannelPrivateError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)


@pytest.mark.asyncio
async def test_collect_skips_non_telegram_source():
    msgs = [make_message(1, "А" * 100, datetime(2024, 6, 1, tzinfo=UTC))]
    client = make_mock_client(msgs)
    source = TelegramSource(client)
    ps = make_person_source(source_type=SourceType.NEWS)

    yielded = []
    async for doc in source.collect(ps):
        yielded.append(doc)

    assert yielded == []


@pytest.mark.asyncio
@pytest.mark.parametrize("error_class", [
    ChannelInvalidError,
    ChannelPrivateError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
    ValueError,
])
async def test_collect_propagates_channel_access_error(error_class):
    client = make_mock_client([], get_entity_raises=error_class)
    source = TelegramSource(client)

    with pytest.raises(error_class):
        async for _ in source.collect(make_person_source()):
            pass
```

- [ ] **Step 2: Run tests, verify failures**

```bash
.venv/bin/python -m pytest tests/sources/test_telegram.py -v
```

Expected:
- `test_collect_skips_non_telegram_source` already passes (impl checks `source_type` since Task 2)
- `test_collect_propagates_channel_access_error` (5 parametrized) — already passes! Бо в Task 2 ми НЕ wrap'или `get_entity` у try/except. Exception propagate'иться natively.

- [ ] **Step 3: Verify no implementation change needed**

Open `src/prophet_checker/sources/telegram.py` і переконайся що `get_entity()` НЕ обгорнуто try/except. Має бути просто:

```python
        channel = person_source.source_identifier
        entity = await self._client.get_entity(channel)
```

Якщо там є try/except — видалити. Source має лишатись pure adapter без error swallowing.

- [ ] **Step 4: Run full test file, verify all pass**

```bash
.venv/bin/python -m pytest tests/sources/test_telegram.py -v
```

Expected: 11 passed (5 prior + 1 structural skip + 5 parametrized propagation).

- [ ] **Step 5: Commit**

```bash
git add tests/sources/test_telegram.py
git commit -m "test(sources): TelegramSource propagates channel-access errors + structural skip for non-Telegram (Task 21)"
```

---

## Task 5: Delete legacy script + verify

**Files:**
- Delete: `scripts/collect_telegram_posts.py`
- Verify: no broken refs in repo

- [ ] **Step 1: Search for remaining references to the script**

```bash
grep -rln "collect_telegram_posts" --include="*.py" --include="*.md" \
  --include="*.toml" --include="*.cfg" --include="*.ini" \
  --include="Makefile" . 2>/dev/null | grep -v __pycache__ | grep -v .venv
```

Expected output: list of files mentioning the script. Likely:
- `scripts/collect_telegram_posts.py` (the file itself)
- `scripts/README.md` (documentation)
- `docs/architecture/2026-04-26-flow-1-telegram-collection.md` (doc reference)
- `docs/architecture/2026-04-26-architecture-current.md` (module inventory)
- maybe `docs/plan/2026-04-08-prophet-checker-plan.md` (historical retrospective)

- [ ] **Step 2: Delete the legacy script**

```bash
git rm scripts/collect_telegram_posts.py
```

- [ ] **Step 3: Update `scripts/README.md` to remove or rewrite the Scenario 1 section**

Read: `scripts/README.md`

Edit the "Scenario 1: Збір даних з Telegram" section. Replace:

```markdown
### 1. Збір даних з Telegram → `data/`

```bash
.venv/bin/python scripts/collect_telegram_posts.py
```

Викачує текстові пости з каналів Telegram, рівномірно семплює по роках, зберігає в `data/<channel>/all.json`.

| Файл | Опис |
|------|------|
| `collect_telegram_posts.py` | Збирач (telethon-based) |
| `tg_session.session` | Telethon auth artifact (gitignored) |
| `data/sample_posts.json` | Канонічний датасет (≈5500 постів, gitignored через розмір) |
| `data/sample_posts_100.json` | Малий sample для швидких тестів |
| `data/arestovich/all.json` | Сирий dump каналу Арестовича |
| `data/zdanov/1.json` | Сирий dump каналу Жданова |
```

With:

```markdown
### 1. Telegram-збір → переселено в `src/prophet_checker/sources/telegram.py`

Логіка переселена в production-модуль (Task 21, 2026-04-29).
Виклик тепер відбувається через `IngestionOrchestrator` (Task 15, planned)
а не через CLI-скрипт.

Історичні artifacts (від попередніх script-runs) залишаються в `data/`:

| Файл | Опис |
|------|------|
| `tg_session.session` | Telethon auth artifact (gitignored) |
| `data/sample_posts.json` | Канонічний multi-author датасет для evals (1049 постів) |
| `data/sample_posts_100.json` | Малий sample для швидких тестів |
| `data/arestovich/all.json` | Сирий dump каналу Арестовича від попереднього script-run |
| `data/zdanov/1.json` | Сирий dump каналу Жданова |
```

- [ ] **Step 4: Update `docs/architecture/2026-04-26-flow-1-telegram-collection.md`**

Read the doc. Replace any reference to `scripts/collect_telegram_posts.py` with `src/prophet_checker/sources/telegram.py`. The Mermaid diagram references should change `Script` node label to `TelegramSource`.

Specifically, find:
```
Script["scripts/collect_telegram_posts.py<br/>collect_channel()"]:::script
```
Replace with:
```
Script["src/prophet_checker/sources/telegram.py<br/>TelegramSource.collect()"]:::script
```

Also update the "Майбутнє переселення (Task 21)" section to indicate it's done.

- [ ] **Step 5: Update `docs/architecture/2026-04-26-architecture-current.md`**

In the Module Inventory table, change:
```
| `scripts/collect_telegram_posts.py` | 🚧 working script | Не модуль — one-off писати в `data/<channel>/all.json`. Майбутнє виносу: Task 21 |
```
To remove this row entirely. Add new row:
```
| `src/prophet_checker/sources/{base,telegram}.py` | ✅ implemented | Source Protocol + TelegramSource adapter (Task 21 done). Yields RawDocument; persistence by orchestrator. |
```

- [ ] **Step 6: Run full test suite to confirm nothing broke**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: All previously-passing tests still pass + 11 new tests in `tests/sources/test_telegram.py` and 3 in `tests/sources/test_protocol.py`. Total ~102 tests.

- [ ] **Step 7: Verify no remaining references**

```bash
grep -rln "collect_telegram_posts" --include="*.py" --include="*.md" . 2>/dev/null | grep -v __pycache__ | grep -v .venv
```

Expected: empty output, OR only historical mentions in `docs/plan/` (retrospective is OK).

- [ ] **Step 8: Commit**

```bash
git add scripts/README.md scripts/collect_telegram_posts.py docs/
git commit -m "refactor(sources): remove legacy collect_telegram_posts.py — superseded by TelegramSource (Task 21)"
```

---

## Final verification

- [ ] **Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 100+ tests passing (88 existing + 14 new).

- [ ] **Verify package structure**

```bash
find src/prophet_checker/sources tests/sources -type f -name "*.py"
```

Expected output:
```
src/prophet_checker/sources/__init__.py
src/prophet_checker/sources/base.py
src/prophet_checker/sources/telegram.py
tests/sources/__init__.py
tests/sources/test_protocol.py
tests/sources/test_telegram.py
```

- [ ] **Verify no broken imports**

```bash
.venv/bin/python -c "
from prophet_checker.sources.base import Source
from prophet_checker.sources.telegram import TelegramSource
print('OK:', Source, TelegramSource)
"
```

Expected: `OK: <class 'prophet_checker.sources.base.Source'> <class 'prophet_checker.sources.telegram.TelegramSource'>`

- [ ] **Confirm legacy script gone**

```bash
ls scripts/collect_telegram_posts.py 2>&1
```

Expected: `ls: scripts/collect_telegram_posts.py: No such file or directory`.

---

## Out of scope (explicitly deferred)

- ❌ **Bootstrap (Person/PersonSource seed records)** — deferred to Task 18 (Alembic migration with seed data)
- ❌ **NewsCollector** — Task 22, out of MVP
- ❌ **Rate-limiting / retry logic** — Task 15 orchestrator's concern
- ❌ **Language detection** — hardcoded `"uk"`, deferred
- ❌ **One-off CLI for bulk-збір** — YAGNI; can revive if needed via `python -m prophet_checker.sources.telegram <channel>` wrapper

---

## Cross-references

- Spec: [`2026-04-29-task-21-telegram-source-design.md`](2026-04-29-task-21-telegram-source-design.md)
- Architecture context: [`../architecture/2026-04-26-flow-production-ingestion.md`](../architecture/2026-04-26-flow-production-ingestion.md)
- Master plan Task 21: [`../plan/2026-04-08-prophet-checker-plan.md`](../plan/2026-04-08-prophet-checker-plan.md)
- Storage interfaces: `src/prophet_checker/storage/interfaces.py`
- Domain models: `src/prophet_checker/models/domain.py`
