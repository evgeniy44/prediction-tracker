# IngestionOrchestrator — Data Flow Sequence Diagram

**Companion document to:** [`2026-05-01-ingestion-orchestrator-design.md`](2026-05-01-ingestion-orchestrator-design.md)

Detailed sequence diagram covering the full ingestion data flow from HTTP trigger through DB commit, including transaction boundaries, branch points, and error paths.

---

## 1. Full happy-path flow

```mermaid
sequenceDiagram
    autonumber
    actor Cron as cron / curl
    participant API as FastAPI<br/>(Task 16)
    participant ORC as IngestionOrchestrator
    participant SR as SourceRepo<br/>(Postgres)
    participant TG as TelegramSource<br/>(Telethon)
    participant EXT as PredictionExtractor
    participant LLM as LLMClient<br/>(Gemini Flash Lite)
    participant EMB as EmbeddingClient<br/>(OpenAI)
    participant PR as PredictionRepo<br/>(Postgres)
    participant DB as Postgres + pgvector

    Cron->>API: POST /ingest/run
    API->>ORC: run_cycle()

    rect rgba(220,235,250,0.4)
    Note over ORC,DB: PHASE 1 — discover active sources
    ORC->>SR: list_active_sources()
    SR->>DB: SELECT * FROM person_sources<br/>WHERE enabled = TRUE
    DB-->>SR: rows
    SR-->>ORC: [PersonSource(ps1, T0), PersonSource(ps2, T0)]
    end

    loop per PersonSource
        rect rgba(250,235,220,0.4)
        Note over ORC,DB: PHASE 2 — collect new posts since cursor
        ORC->>TG: collect(ps, since=ps.last_collected_at)
        TG->>TG: connect Telethon client<br/>iter_messages(channel)
        TG-->>ORC: yield RawDocument(id="tg:arestovich:101", ...)
        end

        loop per RawDocument (async iterator)
            rect rgba(245,235,255,0.4)
            Note over ORC,LLM: PHASE 3 — extract predictions
            ORC->>EXT: extract(text, person_id, doc_id, person_name, pub_date)
            EXT->>LLM: complete(prompt, system=EXTRACTION_SYSTEM)
            LLM-->>EXT: JSON response
            EXT->>EXT: parse_extraction_response()
            EXT-->>ORC: [Prediction(embedding=None), ...] or []
            end

            alt predictions == []
                rect rgba(220,250,220,0.5)
                Note over ORC,DB: BRANCH A — no predictions, advance cursor only
                ORC->>SR: session_factory()
                SR->>DB: BEGIN
                ORC->>SR: update_source_cursor(ps.id, raw_doc.published_at, session)
                SR->>DB: UPDATE person_sources<br/>SET last_collected_at = $1<br/>WHERE id = $2
                ORC->>SR: COMMIT
                SR->>DB: COMMIT
                DB-->>SR: ok
                end
            else predictions non-empty
                rect rgba(255,245,220,0.5)
                Note over ORC,EMB: PHASE 4 — embed each prediction (BEFORE tx)
                loop per prediction (sequential, network I/O)
                    ORC->>EMB: embed(prediction.claim_text)
                    EMB->>EMB: aembedding(<br/>  model="text-embedding-3-small",<br/>  api_key=OPENAI_KEY)
                    EMB-->>ORC: [v1...v1536]
                    ORC->>ORC: prediction.embedding = vector
                end
                end

                rect rgba(220,250,220,0.5)
                Note over ORC,DB: PHASE 5 — atomic save + cursor in single tx
                ORC->>SR: session_factory()
                SR->>DB: BEGIN
                loop per prediction
                    ORC->>PR: save(prediction, session)
                    PR->>DB: INSERT INTO predictions<br/>(id, claim_text, embedding, ...)<br/>VALUES (...)
                end
                ORC->>SR: update_source_cursor(ps.id, raw_doc.published_at, session)
                SR->>DB: UPDATE person_sources<br/>SET last_collected_at = $1
                ORC->>SR: COMMIT
                SR->>DB: COMMIT
                DB-->>SR: ok
                end
            end

            ORC->>ORC: report.posts_seen += 1<br/>report.cursor_advanced_to = raw_doc.published_at
        end
    end

    rect rgba(220,235,250,0.4)
    Note over ORC,API: PHASE 6 — finalize report
    ORC->>ORC: report.finished_at = now()
    ORC-->>API: CycleReport(channels_processed=[...])
    API-->>Cron: 200 OK<br/>{"channels_processed": [...]}
    end
```

---

## 2. Error path — halt-channel-on-error

When any step inside per-channel processing throws (LLM 5xx after retries, embedding API down, DB write fails), the channel halts but other channels continue.

```mermaid
sequenceDiagram
    autonumber
    participant ORC as Orchestrator
    participant TG as TelegramSource
    participant EMB as EmbeddingClient
    participant PR as PredictionRepo
    participant DB as Postgres

    Note over ORC: cursor T0 = ps.last_collected_at

    ORC->>TG: collect(ps, since=T0)
    TG-->>ORC: yield RawDocument(P1, published=T1)

    Note over ORC: post P1 — happy path
    ORC->>EMB: embed(claim)
    EMB-->>ORC: vector
    ORC->>DB: BEGIN tx
    ORC->>PR: save(prediction, session)
    ORC->>PR: update_cursor(ps.id, T1, session)
    ORC->>DB: COMMIT
    Note over ORC: cursor advances T0 → T1

    TG-->>ORC: yield RawDocument(P2, published=T2)

    rect rgba(255,220,220,0.5)
    Note over ORC,EMB: post P2 — embed fails
    ORC->>EMB: embed(claim)
    EMB--xORC: RuntimeError("OpenAI 503")
    Note over ORC: tx NOT opened yet<br/>(embed runs BEFORE BEGIN)
    end

    Note over ORC: caught at channel-level try/except
    ORC->>ORC: ChannelReport.error = "halted at step=processing: ..."
    Note over ORC: cursor stays at T1<br/>NOT advanced past T1

    Note over ORC: break out of channel loop
    Note over ORC: continue to next PersonSource
```

**Recovery on next cycle:**
- `cron` triggers `POST /ingest/run` again
- orchestrator queries active sources — same set
- for halted channel, `last_collected_at = T1` (unchanged from previous halt)
- `TelegramSource.collect(ps, since=T1)` yields P2 fresh
- if embed now works → P2 processed normally, cursor advances T1 → T2

No data loss. No duplicates (predictions for P1 already in DB; P2 had nothing committed).

---

## 3. Multi-channel parallel-safe sequencing

Single `run_cycle()` processes channels sequentially. Halt in one channel does not affect others.

```mermaid
sequenceDiagram
    autonumber
    participant ORC as Orchestrator

    Note over ORC: list_active_sources() → [arestovich, podolyak, gordon]

    rect rgba(220,235,250,0.3)
    Note over ORC: process @arestovich
    ORC->>ORC: 3 posts seen, 2 with predictions, 5 saves<br/>cursor T0 → T3<br/>error=None
    end

    rect rgba(255,220,220,0.3)
    Note over ORC: process @podolyak
    ORC->>ORC: 5 posts seen<br/>post #3 LLM 503 after 3 retries<br/>cursor stays at T1 (after post #2)<br/>error="halted at step=processing"
    end

    rect rgba(220,250,220,0.3)
    Note over ORC: process @gordon
    ORC->>ORC: 1 post seen, 0 predictions, 0 saves<br/>cursor advances<br/>error=None
    end

    Note over ORC: CycleReport.channels_processed:<br/>[<br/>  arestovich: ok, 5 preds<br/>  podolyak: HALTED, 2 preds saved before halt<br/>  gordon: ok, 0 preds<br/>]
```

---

## 4. Transaction boundaries — what's atomic

| Operation | Inside tx? | Why |
|-----------|-----------|-----|
| `list_active_sources()` | Own tx (read) | Auto-commits on session close; not part of post processing |
| `tg_source.collect()` | No | External API call; can't roll back Telegram |
| `extractor.extract()` | No | External API call (LLM) |
| `embedder.embed()` per prediction | **No — explicitly outside** | Network I/O 200-500ms; tying tx open this long would lock rows. All embeds run sequentially BEFORE BEGIN. |
| `prediction_repo.save()` per prediction | **YES — same tx** | Atomic with cursor advance |
| `source_repo.update_source_cursor()` | **YES — same tx** | If save fails, cursor must NOT advance |

**Atomicity rule:** "predictions for post P are saved iff cursor advances past P." Either both happen or neither.

---

## 5. Cursor lifecycle for one PersonSource

```mermaid
stateDiagram-v2
    [*] --> CursorAtT0: PersonSource created<br/>last_collected_at = creation_time
    CursorAtT0 --> ProcessingP1: collect yields P1 (published T1 > T0)
    ProcessingP1 --> CursorAtT1: extract+embed+save<br/>OK; tx commits
    ProcessingP1 --> CursorAtT0: any step fails<br/>tx rollback OR no tx opened
    CursorAtT1 --> ProcessingP2: next iteration
    ProcessingP2 --> CursorAtT2: OK
    ProcessingP2 --> CursorAtT1: fails
    CursorAtT2 --> [*]: cycle ends<br/>(other channels processed too)

    note right of CursorAtT0
        On halt at P1, cursor unchanged
        Next cycle resumes at P1
    end note

    note right of CursorAtT1
        Detection=NO advances cursor too
        (so we don't re-detect non-prediction post)
    end note
```

---

## 6. What this diagram does NOT show

- **Concurrent `run_cycle()` invocations** — Task 16 (FastAPI) responsibility (queue/lock against double-trigger)
- **Real-time monitoring** — separate observability concern
- **Verifier flow** — runs separately (cron job), not part of ingestion cycle
- **RAG/Bot flow** — read-side, not in scope here
- **Alembic migration timing** — runs once at deploy (Task 17), not per-cycle

---

## Cross-references

- **Spec:** [`2026-05-01-ingestion-orchestrator-design.md`](2026-05-01-ingestion-orchestrator-design.md)
- **Implementation plan:** [`2026-05-01-ingestion-orchestrator-plan.md`](2026-05-01-ingestion-orchestrator-plan.md)
- **Source Protocol (Task 21):** `src/prophet_checker/sources/base.py`
