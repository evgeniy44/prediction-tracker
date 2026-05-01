# IngestionOrchestrator — Design Spec

**Status:** approved 2026-05-01 (revised single-tier 2026-05-01)
**Task:** 15 (master plan) / first gap-filler у Flow 5b production-ingestion
**Prerequisites:** ✅ Task 21 (TelegramSource), ✅ LLM Client Split (2026-05-01)
**Next:** Task 16 (FastAPI HTTP-trigger), Task 17-19 (Docker/Alembic/integration smoke)

---

## TL;DR

`IngestionOrchestrator.run_cycle()` — async-функція що приймає HTTP-trigger, ітерує всіх активних `PersonSource` рядків, для кожного збирає нові пости з `TelegramSource` починаючи з `last_collected_at` cursor'а, для кожного поста викликає extraction → (якщо predictions non-empty) embed → save, оновлює cursor після кожного успішного поста. На помилці зупиняє лише поточний канал; інші продовжують. Returns `CycleReport` із summary stats.

Pipeline: **single-tier extraction** (Flash Lite). На постах без передбачень extractor повертає `[]` — orchestrator skip'ає embed/save і просто advance cursor. Detection prefilter як окремий cheap LLM-call — deferred (потребує prompt-engineering + validation поза scope Task 15; spec-revision 2026-05-01).

---

## Architectural Decisions (Q1–Q5)

| # | Decision | Rationale |
|---|----------|-----------|
| Q1 | **Single-tier Flash Lite extraction; "no predictions" detected by `len(extract()) == 0`** | DETECTION_SYSTEM_V2 prompt не існує в codebase (Task 13 eval використовував `len(extractor.extract())` як detection signal). Окремий cheap detection-prompt — scope creep (потребує prompt-engineering + validation). YAGNI — Flash Lite extract ≈ $0.0002/post, копійки. |
| Q2 | **HTTP `POST /ingest/run` обробляє ВСІ активні sources за один тригер** | Найпростіший API — один cron-tick = один HTTP-call. Per-channel виклики — premature optimization (async вже паралелить I/O). |
| Q3 | **Cursor-only dedup через `person_sources.last_collected_at`** | Strict cursor + per-post commits = forward-progress. Documents-existence check — YAGNI (Telegram id стабільні per Task 21). |
| Q4 | **Halt-channel on error, continue other channels** | Industry-standard ETL semantics. Forward-progress на здорових каналах, halt на broken для manual investigation. |
| Q5 | **(N/A — detection prefilter deferred)** | Single-tier означає `PredictionDetector` клас не потрібен. Якщо в майбутньому додамо detection prefilter — буде окремий task. |

---

## Module Layout

```
src/prophet_checker/
  ingestion/                   ← NEW package
    __init__.py
    orchestrator.py            ← IngestionOrchestrator class
    report.py                  ← CycleReport, ChannelReport (Pydantic)

  analysis/
    extractor.py               (existing — unchanged)
    verifier.py                (existing — unchanged)

  sources/
    base.py                    (existing)
    telegram.py                (existing)
    mock.py                    ← NEW: MockSource for tests

  llm/                         (existing — split landed 2026-05-01)
    client.py                  LLMClient.complete()
    embedding.py               EmbeddingClient.embed()
    prompts.py                 EXTRACTION_SYSTEM (existing)

  models/
    domain.py                  ← MODIFIED: add last_collected_at to PersonSource
    db.py                      ← MODIFIED: add last_collected_at column

  storage/
    interfaces.py              ← MODIFIED: add list_active_sources + update_source_cursor methods
    postgres.py                ← MODIFIED: implement новые methods + accept optional session for tx

alembic/versions/
  <rev>_add_last_collected_at_to_person_sources.py  ← NEW migration

tests/
  fakes.py                       ← NEW: shared Fake* repos (extracted from test_storage_interfaces.py)
  test_ingestion_orchestrator.py ← NEW (~9 tests)
  test_ingestion_integration.py  ← NEW (~2 tests)
```

### Class responsibilities

| Клас | Що робить | Constructor deps |
|------|-----------|------------------|
| `IngestionOrchestrator` | Координує: query active sources → per-channel collect → per-post pipeline → cursor advance | `session_factory`, `source_repo`, `prediction_repo`, `extractor`, `embedder`, `sources: dict[SourceType, Source]` |
| `PredictionExtractor` | (existing) extract predictions з `embedding=None`. На LLM error повертає `[]` (silent — orchestrator не може відрізнити "no preds" від "error"). | `llm: LLMClient` |
| `EmbeddingClient` | (existing) text → vector | own |
| `TelegramSource` | (existing) yields `RawDocument` since cursor | Telethon |
| `MockSource` | Returns predefined `RawDocument` list для tests | constructor takes the list |

### `IngestionOrchestrator` API

```python
class IngestionOrchestrator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        source_repo: SourceRepository,
        prediction_repo: PredictionRepository,
        extractor: PredictionExtractor,
        embedder: EmbeddingClient,
        sources: dict[SourceType, Source],
    ) -> None: ...

    async def run_cycle(self) -> CycleReport: ...


class CycleReport(BaseModel):
    started_at: datetime
    finished_at: datetime
    channels_processed: list[ChannelReport]


class ChannelReport(BaseModel):
    person_source_id: str
    posts_seen: int
    posts_with_predictions: int
    predictions_extracted: int
    cursor_advanced_to: datetime | None
    error: str | None = None
```

`sources` parameter — `dict[SourceType, Source]` для multi-source dispatch. MVP: тільки `{SourceType.TELEGRAM: TelegramSource}`.

`session_factory` (не shared session) — кожен post-iteration відкриває свою short-lived session для atomic tx. Pattern: `async with session_factory() as session: async with session.begin(): ...`. Repos приймають optional `session` parameter — якщо передано, використовують його (caller manages tx); якщо ні — opens own session (existing behavior).

---

## Data Flow

```mermaid
sequenceDiagram
    autonumber
    participant API as FastAPI<br/>(Task 16)
    participant ORC as IngestionOrchestrator
    participant SR as SourceRepo
    participant TG as TelegramSource
    participant EXT as Extractor
    participant EMB as Embedder
    participant PR as PredictionRepo

    API->>ORC: run_cycle()
    ORC->>SR: list_active_sources()
    SR-->>ORC: [PersonSource(ps1,arestovich,T0), ...]

    loop per PersonSource
        ORC->>TG: collect(person_source, since=cursor)
        loop per RawDocument (async iterator)
            TG-->>ORC: raw_doc
            ORC->>EXT: extract(raw_doc.raw_text, ...)
            EXT-->>ORC: predictions[] (might be empty)

            alt predictions == []
                rect rgba(200,230,200,0.3)
                Note over ORC,SR: BEGIN tx
                ORC->>SR: update_source_cursor(ps_id, raw_doc.published_at, session)
                Note over ORC,SR: COMMIT
                end
            else predictions non-empty
                loop per prediction (sequential)
                    ORC->>EMB: embed(claim_text)
                    EMB-->>ORC: [v1...v1536]
                end
                rect rgba(200,230,200,0.3)
                Note over ORC,PR: BEGIN tx
                loop per prediction
                    ORC->>PR: save(prediction with embedding, session)
                end
                ORC->>SR: update_source_cursor(ps_id, raw_doc.published_at, session)
                Note over ORC,PR: COMMIT
                end
            end
        end
    end

    ORC-->>API: CycleReport
```

### Semantic invariants

1. **Cursor advances after every fully-processed post** — як на `predictions==[]` (no save), так і на non-empty (з saves). Never re-process a previously-seen post.
2. **Embeds виконуються ПЕРЕД transaction**. Network I/O (200-500ms per call) поза tx-scope — не тримати DB-lock'и.
3. **Per-post atomic transaction**. predictions saves + cursor update — в одній `AsyncSession.begin()` block. Будь-яка помилка → rollback всього + cursor не зрушується.
4. **Re-processing safety**. На halt: cursor залишається на last successful post. Наступний цикл retry'їть з того ж місця. Прогон на свіжому стані (нові uuid4 для predictions) — no duplicates бо в DB ще нема.

### Known limitation: extraction errors are silent

`PredictionExtractor.extract()` swallows LLM exceptions і повертає `[]`. Orchestrator не може відрізнити "пост без передбачень" від "extraction впала":
- "no predictions" → cursor advances ✓ correct
- "extraction error" → cursor also advances ✗ silent skip

LiteLLM `num_retries=3` з backoff покриває transient errors. Persistent errors лишають слід в логах (через `logger.exception` всередині extractor). Production моніторинг повинен alert'ити на extraction-error spike в логах.

Якщо в майбутньому знадобиться halt-on-error для extraction: refactor `extractor.extract()` щоб raise — окремий cleanup task поза Task 15.

### Error path

```mermaid
flowchart LR
    A[post P fails<br/>LLM/DB error] --> B[log.error<br/>з channel + post_id + step]
    B --> C[break out of channel loop]
    C --> D[ChannelReport.error = str e]
    D --> E[continue to next channel]
    E --> F[other channels<br/>unaffected]

    style A fill:#fdd
    style B fill:#fed
    style F fill:#dfd
```

`run_cycle()` завжди завершується успішно (з точки зору FastAPI) — caller бачить `CycleReport`. Halted channels мають `error` field set.

---

## Data Model + Migration

### Pydantic domain (`src/prophet_checker/models/domain.py`)

```python
class PersonSource(BaseModel):
    id: str
    person_id: str
    source_type: SourceType
    source_identifier: str
    enabled: bool = True
    last_collected_at: datetime | None = None   # NEW

    def model_post_init(self, __context) -> None:
        if self.last_collected_at is None:
            self.last_collected_at = datetime.now(UTC)
```

Default = creation time (через `model_post_init`). Семантика: новий source починає з моменту створення row. Historical backfill — manual SQL.

### SQLAlchemy DB model (`src/prophet_checker/models/db.py`)

```python
last_collected_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    server_default=func.now(),
)
```

`NOT NULL` + `server_default=NOW()` — ніяких NULL-edge cases в коді.

### Alembic migration

```python
def upgrade():
    op.add_column(
        "person_sources",
        sa.Column(
            "last_collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

def downgrade():
    op.drop_column("person_sources", "last_collected_at")
```

Backfill існуючих rows автоматичний через `server_default=NOW()`.

### Storage API additions

Додаємо методи до існуючого `SourceRepository` Protocol (не сплітимо клас — додаємо ad-hoc):

```python
# storage/interfaces.py
class SourceRepository(Protocol):
    # existing methods unchanged
    async def list_active_sources(self) -> list[PersonSource]: ...
    async def update_source_cursor(
        self,
        person_source_id: str,
        cursor: datetime,
        session: AsyncSession | None = None,   # NEW: tx-aware
    ) -> None: ...
```

```python
# storage/postgres.py
class PostgresSourceRepository:
    async def list_active_sources(self) -> list[PersonSource]:
        # SELECT * FROM person_sources WHERE enabled = TRUE
        ...

    async def update_source_cursor(
        self,
        person_source_id: str,
        cursor: datetime,
        session: AsyncSession | None = None,
    ) -> None:
        # UPDATE person_sources SET last_collected_at = :cursor WHERE id = :id
        # If session passed: use it (caller's tx); else open own session
        ...
```

`PredictionRepository.save` теж оновлюємо щоб приймати optional session:

```python
class PredictionRepository(Protocol):
    async def save(
        self,
        prediction: Prediction,
        session: AsyncSession | None = None,
    ) -> Prediction: ...
```

### Transaction primitive

Orchestrator використовує `session_factory` (не shared session) — кожен post-iteration відкриває свою short-lived session. Pattern:

```python
async with self._session_factory() as session:
    async with session.begin():
        for p in predictions:
            await self._prediction_repo.save(p, session=session)
        await self._source_repo.update_source_cursor(
            ps.id, raw_doc.published_at, session=session
        )
# auto-commit on `__aexit__`; auto-rollback on exception
```

Repos з optional `session` parameter:
- `session is not None` → repo додає в session, НЕ commit'ить (caller manages tx)
- `session is None` → repo opens own session via factory + commits (existing standalone behavior)

Це backward-compatible: existing callers що не використовують tx — продовжують працювати.

---

## Error Handling

| Step | Можливі помилки | Поведінка |
|------|------------------|-----------|
| `tg_source.collect()` | `ChannelPrivateError`, `FloodWaitError`, network | Halt channel — TelegramSource піднімає (Task 21); orchestrator catches → log + skip |
| `extractor.extract()` | swallows internally → returns `[]` | **Silent skip** — orchestrator advances cursor (known limitation, see "Semantic invariants") |
| `embedder.embed()` | `litellm.APIError`, network | Halt channel — embed ПЕРЕД tx, тож commit ще не стався |
| `prediction_repo.save()` | `IntegrityError`, `OperationalError` | Halt channel — tx rollback автоматичний |
| `source_repo.update_source_cursor()` | те саме | Halt channel — rollback включає saves |

**НЕ ловимо:**
- `KeyboardInterrupt`, `SystemExit` — clean shutdown
- `pydantic.ValidationError` на domain-моделях — bug у нашому коді, fail loud

**Structured logging:**

```python
logger.error(
    "ingestion: channel halted on post",
    extra={
        "person_source_id": ps.id,
        "channel": ps.source_identifier,
        "document_id": raw_doc.id,
        "step": "embed",
        "exception": str(exc),
    },
)
```

`ChannelReport.error` = коротке текстове резюме (`"halted on post tg:arestovich:12345 at step=embed"`). Деталі — в логах.

---

## Testing Strategy

### Layer 1: Orchestrator unit (`tests/test_ingestion_orchestrator.py`)

Mocks: `Source`, `Extractor`, `Embedder`, repos (Fake* з `tests/fakes.py`). Тестуємо control flow:

| Test | Сценарій |
|------|----------|
| `test_run_cycle_no_active_sources` | repo.list_active_sources() → []; report.channels=[] |
| `test_run_cycle_processes_posts_in_one_channel` | 3 posts, 2 з predictions; assert extract×3, embeds×N, saves×N |
| `test_empty_predictions_advances_cursor_without_save` | extract→[]; assert update_source_cursor called, no save calls |
| `test_non_empty_predictions_extracts_embeds_saves_atomically` | check tx usage: saves всередині `session.begin()` block |
| `test_embed_failure_halts_channel_no_save` | embed throws; assert no save calls; cursor not advanced; report.error set |
| `test_save_failure_rollbacks_and_halts` | save throws on 3rd of 5; assert rollback (no saves committed); cursor not advanced |
| `test_one_channel_halt_does_not_block_others` | 2 channels; ch1 embed fails on post 2; ch2 processes fully |
| `test_cursor_advances_per_post` | 3 posts → update_source_cursor called 3 times with each post's published_at |
| `test_cycle_report_aggregates_counts` | report.channels[0].predictions_extracted == sum across posts |

**~9 тестів.**

### Layer 2: Integration smoke (`tests/test_ingestion_integration.py`)

Через **`MockSource`** (`src/prophet_checker/sources/mock.py`):

```python
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

Реалізує `Source` Protocol з `sources/base.py` (Task 21).

Test: real `IngestionOrchestrator` + `MockSource` + mocked LLM (`AsyncMock`) + **shared Fake* repos** (extracted з `tests/test_storage_interfaces.py` в `tests/fakes.py`, з новими методами `list_active_sources` + `update_source_cursor`).

| Test | Сценарій |
|------|----------|
| `test_end_to_end_three_posts_with_mocked_llm` | Happy path: 3 posts → 5 predictions saved + cursor advances |
| `test_halt_recovery_resumes_from_last_cursor` | Cycle 1 fails on post 2; cycle 2 picks up from post 2 |

**~2 тести.**

### Test count delta

- +9 orchestrator unit
- +2 integration
- **+11 tests**

Поточних 101 + 11 = **112** після Task 15.

### Чого НЕ тестуємо тут

- ❌ Real Telegram API — manual / Task 19
- ❌ Real OpenAI/Gemini — manual / Task 19
- ❌ Real Postgres + pgvector — Task 19
- ❌ Concurrent `run_cycle()` calls — Task 16 problem (FastAPI `BackgroundTasks` queue)
- ❌ Performance/latency — moot until production traffic

---

## Out of Scope (explicitly deferred)

- ❌ **Two-tier extraction** (Flash Lite → Pro Preview as judge filter) — needs proof-of-concept на ~50 постах. Майбутній рефактор.
- ❌ **FastAPI HTTP endpoint** — Task 16. Цей дизайн tільки `run_cycle()` API.
- ❌ **Bot frontend** — Phase 2 (separate brainstorm).
- ❌ **Verifier orchestration** — Verifier v2 designed, але запускається окремо (cron / scheduled task), не як частина ingestion-cycle.
- ❌ **Re-embed missing** — якщо embed впав → halt channel, не save with `embedding=NULL`. YAGNI поки не побачимо real failure rates.
- ❌ **Per-post failure count + dead-letter** — деплоємо MVP simple halt-on-error; стрімкі retries додамо коли побачимо stuck channels.
- ❌ **NewsCollector** (other source types) — `sources` dict spec'нутий extensible-ним, але implementation NEWS — не в MVP.
- ❌ **Concurrent cycle protection** — Task 16 (FastAPI має queue/lock проти двох одночасних `run_cycle()`).

---

## Cross-references

- **LLM Client Split** (prerequisite, ✅ done): [`2026-05-01-llm-client-split-design.md`](2026-05-01-llm-client-split-design.md)
- **Task 21 TelegramSource** (prerequisite, ✅ done): [`2026-04-29-task-21-telegram-source-plan.md`](2026-04-29-task-21-telegram-source-plan.md)
- **Architecture overview**: [`../architecture/2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md)
- **Production ingestion flow** (5b): [`../architecture/2026-04-26-flow-production-ingestion.md`](../architecture/2026-04-26-flow-production-ingestion.md)
- **Master plan**: [`../plan/2026-04-08-prophet-checker-plan.md`](../plan/2026-04-08-prophet-checker-plan.md)
- **Detection eval** (Task 13, validated DETECTION_SYSTEM_V2): [`../architecture/2026-04-26-flow-3-detection-eval.md`](../architecture/2026-04-26-flow-3-detection-eval.md)
