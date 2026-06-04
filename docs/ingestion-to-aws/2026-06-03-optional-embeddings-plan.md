# Optional embeddings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let ingestion run without an OpenAI key by skipping claim embeddings; embeddings are **off by default**, enabled only via `EMBEDDINGS_ENABLED=true`.

**Architecture:** `embeddings_enabled` config flag (default **False**); factory builds the `EmbeddingClient` only when enabled, else passes `embedder=None`; the orchestrator guards its embed loop on `embedder is not None`. No CLI flag — `run_ingestion.py` / `app.py` are unchanged (they read `Settings()`, which now defaults to no embeddings).

**Tech Stack:** Python 3.12, async, pydantic-settings, SQLAlchemy async, pytest (`asyncio_mode=auto`).

**Spec:** `docs/ingestion-to-aws/2026-06-03-optional-embeddings-design.md` (`3d3b0b8`).

**Working dir:** prefix every command with `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker`.

**Test baseline:** 202 passed. Final expected: 203 (+1 T1).

**Behavior note:** default False flips embeddings off for ALL ingestion (incl. `POST /ingest/run`) until `.env` sets `EMBEDDINGS_ENABLED=true`. Intended ("поки").

---

## File Structure

| File | Change |
|---|---|
| `src/prophet_checker/config.py` | add `embeddings_enabled: bool = False` |
| `src/prophet_checker/factory.py` | build embedder only if enabled, else `None` |
| `src/prophet_checker/ingestion/orchestrator.py` | guard embed loop on `embedder is not None` |
| `tests/test_ingestion_orchestrator.py` | embedder=None → embed skipped test |
| `docs/verification-track/20-verification-orchestrator/real-db-smoke.md` | note: embeddings off by default |

**Models:** T1 SONNET (logic), T2 HAIKU.

---

### Task 1: Optional embedder (config + factory + orchestrator guard)

**Files:**
- Modify: `src/prophet_checker/ingestion/orchestrator.py` (embed loop, ~lines 69-71)
- Modify: `src/prophet_checker/config.py` (Settings fields)
- Modify: `src/prophet_checker/factory.py` (embedder block, ~lines 37-40)
- Test: `tests/test_ingestion_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ingestion_orchestrator.py`:

```python
async def test_run_cycle_skips_embedding_when_no_embedder():
    person_source = PersonSource(
        id="ps1", person_id="p1", source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    doc = RawDocument(
        id="tg:arestovich:1", person_id="p1", source_type=SourceType.TELEGRAM,
        url="https://t.me/arestovich/1",
        published_at=datetime(2024, 1, 5, tzinfo=UTC), raw_text="Post",
    )
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    prediction_repo = FakePredictionRepo()
    pred = Prediction(
        id="pred-1", document_id="tg:arestovich:1", person_id="p1",
        claim_text="claim", prediction_date=date(2024, 1, 1),
    )
    extractor = MagicMock()
    extractor.extract = AsyncMock(side_effect=[[pred]])
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory, source_repo=source_repo,
        prediction_repo=prediction_repo, extractor=extractor,
        embedder=None, sources={SourceType.TELEGRAM: MockSource([doc])},
    )

    await orchestrator.run_cycle()

    assert len(prediction_repo._predictions) == 1
    assert prediction_repo._predictions[0].embedding is None
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_run_cycle_skips_embedding_when_no_embedder -v`
Expected: FAIL — `len(prediction_repo._predictions) == 1` is false. With `embedder=None`, the loop calls `None.embed(...)` → `AttributeError`, caught by `_process_channel`'s try/except (sets `report.error`), so the prediction is never saved → `_predictions` is empty.

- [ ] **Step 3: Guard the embed loop**

In `src/prophet_checker/ingestion/orchestrator.py`, the predictions branch becomes:

```python
                if predictions:
                    report.posts_with_predictions += 1
                    if self._embedder is not None:
                        for p in predictions:
                            p.embedding = await self._embedder.embed(p.claim_text)
                    async with self._session_factory() as session:
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_run_cycle_skips_embedding_when_no_embedder -v`
Expected: PASS (embed skipped; prediction saved with default `embedding=None`).

- [ ] **Step 5: Add the config flag (default False)**

In `src/prophet_checker/config.py`, add this field to `Settings` (after `openai_api_key`):

```python
    embeddings_enabled: bool = False
```

- [ ] **Step 6: Make the factory build it conditionally**

In `src/prophet_checker/factory.py`, replace the unconditional embedder block:

```python
    embedder = EmbeddingClient(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )
```

with:

```python
    embedder = None
    if settings.embeddings_enabled:
        embedder = EmbeddingClient(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )
```

- [ ] **Step 7: Run full suite + config check**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "from prophet_checker.config import Settings; from prophet_checker.factory import build_verification_orchestrator; assert Settings().embeddings_enabled is False; print('config OK')" && .venv/bin/python -m pytest -q`
Expected: `config OK`; full suite **203 passed**. (If `config OK` fails, your local `.env` sets `EMBEDDINGS_ENABLED` — that's fine, skip the assert.)

- [ ] **Step 8: Commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/config.py src/prophet_checker/factory.py src/prophet_checker/ingestion/orchestrator.py tests/test_ingestion_orchestrator.py
git commit -m "$(cat <<'EOF'
feat(ingestion): опційні embeddings (embeddings_enabled default False)

factory будує EmbeddingClient лише якщо enabled; orchestrator пропускає embed
коли embedder=None. Default off — ingestion gemini-only без OpenAI (вмикається
через .env EMBEDDINGS_ENABLED=true).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Note in the real-DB smoke runbook

**Files:**
- Modify: `docs/verification-track/20-verification-orchestrator/real-db-smoke.md`

- [ ] **Step 1: Add the note**

In `real-db-smoke.md`, Step 1 "Варіант A", immediately after the `run_ingestion.py` command block (the line starting "Очікувано: рядок `ps:@arestovich:...`"), append:

```markdown

> Embeddings за замовчуванням вимкнені (`EMBEDDINGS_ENABLED=False`) — `OPENAI_API_KEY` не потрібен, лише `GEMINI_API_KEY` + Postgres. Прогнози просто не будуть RAG-searchable. Щоб увімкнути — `EMBEDDINGS_ENABLED=true` у `.env`.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add docs/verification-track/20-verification-orchestrator/real-db-smoke.md
git commit -m "$(cat <<'EOF'
docs(verifier): real-db-smoke нотатка — embeddings off за замовчуванням

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final Verification

- [ ] **Full suite**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest -q`
Expected: **203 passed**.

- [ ] **Git state**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git log --oneline -2 && git status --short | grep -v "^??"`
Expected: 2 task commits; working tree clean (tracked).

- [ ] **Scope discipline**

Confirm NOT modified: `alembic/`, `models/`, `app.py`, `scripts/run_ingestion.py`, `llm/embedding.py`. This task touches only `config.py`, `factory.py`, `ingestion/orchestrator.py`, the test file, and the runbook.
