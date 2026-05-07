# Integration Smoke Script — Design Spec (Task 19)

**Status:** approved 2026-05-07
**Task:** 19 (master plan) — Final gate перед declaring MVP ingestion done. Validates real Postgres + Telegram + Gemini + OpenAI integration end-to-end.
**Prerequisites:** ✅ Task 15 (orchestrator), ✅ Task 16 (FastAPI), ✅ Task 17 (Docker Compose + baseline migration), ✅ TelegramSource ordering fix (commit `0238b61`)
**Next:** Production deployment track (AWS deploy = окремий task)

---

## TL;DR

Standalone Python script `scripts/integration_smoke.py` що runs ad-hoc проти real services. Component-level checks (`postgres → telegram → gemini → openai → e2e`) з clear diagnostics per stage. CLI args для scope control: `--channel` + `--limit` обов'язкові, `--component` для targeted run, `--reset-db` для clean slate.

Self-seeds `PersonSource` row для testing. Writes persist у real Postgres (cursor advances, predictions saved). Default cursor = epoch (full-history capable; user controls via `--limit`).

---

## Architectural Decisions (Q1–Q4)

| # | Decision | Rationale |
|---|----------|-----------|
| Q1 | **Standalone Python script** (`scripts/integration_smoke.py`) | Manual smoke = ad-hoc validation. Pytest test для одноразового smoke — overengineered. Markdown checklist — зеро enforcement. Script gives CLI control + JSON output + exit codes без pytest overhead. |
| Q2 | **Component-level checks + e2e stage**, runner викликає sequentially | Pet-project value: через 3 місяці треба перевірити "чи API ключі ще валідні" — діагностика на specific service. Single-flow smoke ховає WHICH service broke. |
| Q3 | **Self-seeding `PersonSource` row** на first run | Zero manual setup — `python scripts/integration_smoke.py --channel X --limit 1` працює одразу. Idempotent: re-runs не дублюють. |
| Q4 | **Required `--channel` + `--limit`, no defaults** | Forces explicit scope per run. No accidental expensive bulk-loads. User chooses cheap (`--limit 1`) vs full-history (`--limit 99999`) кожного разу. |

---

## CLI surface

```bash
# Cheap smoke — 1 newest post
python scripts/integration_smoke.py --channel @arestovich --limit 1

# Full history bulk-load
python scripts/integration_smoke.py --channel @arestovich --limit 99999

# Targeted single component (no API costs якщо postgres-only)
python scripts/integration_smoke.py --channel @arestovich --limit 1 --component postgres

# Don't halt on first fail — run everything, collect all errors
python scripts/integration_smoke.py --channel @arestovich --limit 1 --keep-going

# Drop smoke PersonSource row + cascading predictions перед run
python scripts/integration_smoke.py --channel @arestovich --limit 1 --reset-db

# Help
python scripts/integration_smoke.py --help
```

### Args matrix

| Arg | Required? | Type | Description |
|-----|-----------|------|-------------|
| `--channel` | **YES** | str | Telegram channel username (без `@` accepted також) |
| `--limit` | **YES** | int | Max posts to process per cycle. Орendiental cost: ~$0.001 × N |
| `--component` | no | str ∈ `{postgres, telegram, gemini, openai, e2e}` | Run only specified stage; skip others |
| `--keep-going` | no | flag | Don't halt on first fail; run all stages, accumulate errors |
| `--reset-db` | no | flag | Drop smoke `PersonSource` (id=`smoke-test`) + cascading rows перед run |

---

## File layout

```
scripts/
  integration_smoke.py     ← NEW (~250 рядків)
docs/ingestion-to-aws/
  2026-05-07-integration-smoke-design.md   ← this spec
  2026-05-07-integration-smoke-plan.md     ← plan (next step)
```

ОДИН Python файл. Все configurable через CLI args + `.env` (для API keys, Settings вже існує).

---

## Component checks

### Stage 1: `postgres`

**Що робить:**
- Connect to `localhost:5432` через existing `Settings.database_url`
- Query `SELECT version_num FROM alembic_version` → assert row exists і matches expected baseline (`edb2e385f26b`)
- Query `SELECT extname FROM pg_extension WHERE extname='vector'` → assert `vector` row exists

**Pass criterion:** обидві queries succeed з expected результатами.

**Fail signals:**
- `OperationalError: could not connect` → "Did you `docker compose up -d`?"
- `alembic_version` empty → "Did you `alembic upgrade head`?"
- `vector` extension missing → migration not applied properly (regression в `edb2e385f26b`)

**Cost:** $0 (local Postgres only).

### Stage 2: `telegram`

**Що робить:**
- Build TelegramClient using `Settings.telegram_api_id`, `Settings.telegram_api_hash`, `Settings.tg_session_path`
- `await client.start()` (auths via existing `.session` file; FAILS if session not present — script reports clear msg)
- `entity = await client.get_entity(channel)` (validates channel exists, public)
- `messages = await client.iter_messages(entity, limit=3)` collected into list
- Assert `len(messages) >= 1`
- Disconnect cleanly

**Pass criterion:** entity resolves AND принаймні 1 message returned.

**Fail signals:**
- `tg_session.session` missing → "Run interactive auth: `python -m prophet_checker` once and complete OTP flow"
- `ChannelPrivateError` → "Channel is private or doesn't exist: {channel}"
- `FloodWaitError` → "Telegram rate limited; retry in N seconds"

**Cost:** $0 (Telegram API is free for read of public channels).

### Stage 3: `gemini`

**Що робить:**
- Build LLMClient using `Settings.llm_provider="gemini"` + `Settings.llm_model="gemini-2.0-flash-lite-preview"` (or Task 13 winner config) + `Settings.llm_api_key` (Gemini key)
- Call `await llm_client.complete(prompt=SAMPLE_PROMPT, system=EXTRACTION_SYSTEM)` з hardcoded sample text
- Parse response через `parse_extraction_response`
- Assert response is `list[dict]` (empty OR з extracted predictions — both valid)

**Pass criterion:** API call succeeds (no exception), response parses до Python list.

**Fail signals:**
- `litellm.AuthenticationError` → "Invalid GEMINI_API_KEY або wrong provider config"
- `litellm.RateLimitError` → "Gemini rate limited; LiteLLM retried 3× з backoff і все одно failed"
- Parse error → "LLM returned non-JSON response — prompt drift?"

**Sample text:** `"15 жовтня закінчиться війна, до Києва прибуде делегація НАТО з гарантіями безпеки до кінця року."` (короткий test text з guaranteed prediction).

**Cost:** ~$0.0002 per stage run (single Gemini Flash Lite call).

### Stage 4: `openai`

**Що робить:**
- Build EmbeddingClient using `Settings.openai_api_key` + `Settings.embedding_model="text-embedding-3-small"`
- Call `await embedder.embed(text=SAMPLE_CLAIM)` з hardcoded sample
- Assert returned `list[float]` має `len == 1536`

**Pass criterion:** API succeeds, vector має правильну розмірність.

**Fail signals:**
- `litellm.AuthenticationError` → "Invalid OPENAI_API_KEY"
- Wrong dimensions → "Wrong embedding model? Expected text-embedding-3-small (1536 dims)"

**Sample claim:** `"Контрнаступ почнеться влітку 2024 року"` (short Ukrainian text).

**Cost:** ~$0.00002 per stage run.

### Stage 5: `e2e`

**Що робить:**
1. Self-seed `PersonSource` row якщо не існує (id=`smoke-test`):
   - Якщо `--reset-db` flag passed — drop existing row + cascading predictions FIRST
   - Якщо row exists — leave as-is (incremental smoke runs use existing cursor)
   - Якщо не exists — create з `last_collected_at = epoch (1970-01-01 UTC)` (full history default)
2. Build full `IngestionOrchestrator` через `factory.build_orchestrator(settings, stack)` (existing Task 16 wiring)
3. Override orchestrator's `--limit` semantic: passed as parameter to TelegramSource (Note: requires plumbing — see "Implementation note" below)
4. Call `await orchestrator.run_cycle()` — full real flow
5. Assert `report.channels_processed[0].error is None`
6. Print `CycleReport` JSON to stdout

**Pass criterion:** cycle completes with no per-channel error; report serializes correctly.

**Fail signals:**
- per-channel `error` field set → orchestrator halted на something (extraction/embed/save)
- Empty `channels_processed` → smoke PersonSource not enabled (bug)

**Cost:** ~$0.001 × `--limit` per stage run.

#### Implementation note: how does `--limit` reach orchestrator?

Current `IngestionOrchestrator.run_cycle()` НЕ has `limit` parameter. TelegramSource collect() yields ALL messages > since без built-in limit (Telethon's `limit` parameter exists but TelegramSource doesn't expose it).

**Two approaches:**

**A. Add limit early-break у smoke script wrapper (recommended for Task 19)**
- Smoke script wraps `orchestrator.run_cycle()` НЕ напряму — instead reuses orchestrator's components but adds early-break logic
- Або: smoke script monkey-patches TelegramSource to use Telethon's `iter_messages(..., limit=N)`
- **Pro:** не змінює production orchestrator code
- **Contra:** smoke script реалізує custom flow (не тестує точну production code path)

**B. Add limit parameter to orchestrator (production change)**
- `IngestionOrchestrator.run_cycle(per_channel_limit: int | None = None)`
- TelegramSource gets `--per-channel-limit` plumbed
- **Pro:** future-proofs for production scenarios (cron з max load cap)
- **Contra:** scope creep — не ясно чи production needs це

**Decision: A.** Pet project, smoke is wrapper, не production. Smoke script монkey-patches TelegramSource при e2e stage:

```python
async def _patched_collect(person_source, since, _limit=N):
    # Wraps original collect, breaks after N yields
    count = 0
    async for doc in original_collect(person_source, since):
        if count >= _limit:
            break
        yield doc
        count += 1
```

Або еквівалентний wrapper. Smoke verifies е2е flow з-за обмеженого input.

---

## Self-seeding logic

```python
SMOKE_PS_ID = "smoke-test"
SMOKE_PERSON_ID = "smoke-test-person"
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


async def _ensure_smoke_person_source(session_factory, channel: str, reset: bool):
    async with session_factory() as session:
        if reset:
            # Cascading delete: predictions FK → raw_documents FK → person → person_source
            await session.execute(
                text("DELETE FROM predictions WHERE person_id = :pid"), {"pid": SMOKE_PERSON_ID}
            )
            await session.execute(
                text("DELETE FROM raw_documents WHERE person_id = :pid"), {"pid": SMOKE_PERSON_ID}
            )
            await session.execute(
                text("DELETE FROM person_sources WHERE id = :id"), {"id": SMOKE_PS_ID}
            )
            await session.execute(
                text("DELETE FROM persons WHERE id = :pid"), {"pid": SMOKE_PERSON_ID}
            )
            await session.commit()

        existing = await session.execute(
            select(PersonSourceDB).where(PersonSourceDB.id == SMOKE_PS_ID)
        )
        if existing.scalar_one_or_none() is None:
            session.add(PersonDB(id=SMOKE_PERSON_ID, name="Smoke Test"))
            session.add(PersonSourceDB(
                id=SMOKE_PS_ID,
                person_id=SMOKE_PERSON_ID,
                source_type="telegram",
                source_identifier=channel,
                enabled=True,
                last_collected_at=EPOCH,
            ))
            await session.commit()
```

`EPOCH` cursor — orchestrator's `since` буде epoch, TelegramSource yields all history (cost capped via `--limit` wrapper).

---

## Output format

### Success path

```
[1/5] postgres connect + pgvector ext + alembic head           ✓ (0.12s)
[2/5] telegram client connect + iter_messages (@arestovich)    ✓ (1.43s)  3 messages
[3/5] gemini Flash Lite extract on sample                      ✓ (2.81s)  ~$0.0002
[4/5] openai embed on sample (1536-dim vector)                 ✓ (0.31s)
[5/5] e2e cycle (limit=1, channel=@arestovich)
      seeded PersonSource id=smoke-test (cursor=epoch)
      processed 1 post, 1 with predictions, 3 saved
      cursor advanced 1970-01-01 → 2026-05-06
                                                               ✓ (4.12s)  ~$0.0014

PASS in 8.79s (~$0.0016 total)
```

### Fail path

```
[1/5] postgres connect + pgvector ext + alembic head           ✓ (0.12s)
[2/5] telegram client connect + iter_messages (@arestovich)    ✓ (1.43s)  3 messages
[3/5] gemini Flash Lite extract on sample                      ✗ (0.34s)
      AuthenticationError: 401 Unauthorized — invalid GEMINI_API_KEY

FAIL at stage 3 (gemini) after 1.89s
```

З `--keep-going`:

```
[3/5] gemini ... ✗ AuthenticationError
[4/5] openai ... ✓ (0.31s)
[5/5] e2e ... ✗ (depends on gemini)
       skipped — upstream fail

FAIL: 2 stages failed (gemini, e2e)
```

### Exit codes

- `0` — all selected stages pass
- `1` — any stage fail

---

## Pre-conditions

Script ASSUMES:
- `.env` filled з real API keys: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `LLM_API_KEY` (Gemini), `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
- `tg_session` file exists (Telethon already auth'нутий) — first-time user runs interactive auth окремо
- `docker compose up -d` already running
- `alembic upgrade head` already applied

If будь-яке fail'ить — script exits early з diagnostic message ("postgres unreachable: did you `docker compose up -d`?", etc.).

---

## Out of Scope

- ❌ **CI integration** — manual smoke. GitHub Actions додамо при AWS deploy.
- ❌ **Recorded fixtures** (vcr.py) — кожен run hits real services. Cost $0.001 виправдовує.
- ❌ **Failure injection** (rate limit simulation, channel deletion) — manual smoke tests success path. Failure recovery — orchestrator unit tests already cover.
- ❌ **Performance benchmarking** — informal latency через progress timestamps.
- ❌ **Cleanup of e2e DB writes** — predictions persist. `--reset-db` opt-in cleanup.
- ❌ **Multi-channel smoke** — `--channel` accepts ОДИН channel per run. Test multiple → multiple invocations.
- ❌ **Telegram interactive auth bootstrap** — assume session file already present. Document workflow в README якщо ще нема.
- ❌ **Automated tests for smoke script itself** — script IS the test.

---

## Cross-references

- **Task 17 Docker Compose:** [`2026-05-07-docker-compose-design.md`](2026-05-07-docker-compose-design.md)
- **Task 16 FastAPI:** [`2026-05-05-fastapi-http-trigger-design.md`](2026-05-05-fastapi-http-trigger-design.md)
- **Task 15 IngestionOrchestrator:** [`2026-05-01-ingestion-orchestrator-design.md`](2026-05-01-ingestion-orchestrator-design.md)
- **TelegramSource ordering fix (commit `0238b61`)** — prerequisite, surfaced during this brainstorm
- **Architecture overview:** [`../architecture/2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md)
