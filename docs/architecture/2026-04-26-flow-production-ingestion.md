# Flow: Production Ingestion (planned)

**Дата:** 2026-04-26
**Status:** 📋 designed only — Task 15 implements
**Index:** [`2026-04-26-architecture-current.md`](2026-04-26-architecture-current.md)

Цільовий потік даних: scheduler → collect → save → detect → extract → save prediction. Це частина Flow 5b з оригіналу; verification subflow винесена в [`verifier-v2/`](../verifier-v2/), RAG subflow в [`2026-04-26-flow-production-rag.md`](2026-04-26-flow-production-rag.md).

---

```mermaid
flowchart TD
    Sched[/"📋 Scheduler<br/>(cron-like, e.g. APScheduler)"/]:::actor
    Orch["📋 IngestionOrchestrator<br/>src/prophet_checker/<br/>ingestion.py"]:::orch

    SR1["PostgresSourceRepository<br/>.get_person_sources(enabled=True)"]:::step
    Sources["📋 src/sources/&lt;type&gt;.py<br/>Source.collect(since=last_collected_at)"]:::step
    SR2["PostgresSourceRepository<br/>.save_document(RawDocument)<br/>(dedupe by URL)"]:::step
    SR3["PostgresSourceRepository<br/>.get_unprocessed_documents()"]:::step

    Detect["📋 PredictionDetector<br/>.has_prediction(text) → bool<br/>cheap model (Flash Lite, F1=0.848)<br/>skips ~80% of posts"]:::detect

    Extr["PredictionExtractor<br/>.extract(doc.text, ...) → list[Prediction]<br/>+ LLMClient.embed() для embedding"]:::step

    PR["PostgresPredictionRepository<br/>.save(prediction)"]:::step
    VS["PostgresVectorStore<br/>.store_embedding(pred_id, embedding)"]:::step

    DB[("Postgres<br/>(predictions + raw_documents)")]:::store

    Sched -- "trigger every N hours" --> Orch
    Orch --> SR1
    SR1 -- "for each person+source" --> Sources
    Sources --> SR2 --> DB
    DB --> SR3
    SR3 -- "for each unprocessed doc" --> Detect

    Detect -- "has_prediction = false<br/>(skip — saves cost)" --> Skip[/"❌ skip extraction"/]:::skip
    Detect -- "has_prediction = true" --> Extr
    Extr --> PR --> DB
    PR --> VS --> DB

    classDef actor fill:#2a2a4a,stroke:#88c5ff,color:#fff,stroke-width:2px
    classDef orch fill:#553300,stroke:#fff,color:#fff,stroke-width:2px
    classDef step fill:#2a3a55,stroke:#88c5ff,color:#fff
    classDef detect fill:#003355,stroke:#fff,color:#fff,stroke-width:2px
    classDef store fill:#1a4a2a,stroke:#88ff88,color:#fff
    classDef skip fill:#553333,stroke:#fff,color:#fff
```

## Required gap-fillers

- 📋 **Task 15** — `src/prophet_checker/ingestion.py:IngestionOrchestrator`
- 📋 **Task 16** — FastAPI app entry (`__main__.py`) — exposes orchestrator endpoint
- 📋 **Task 21** — `src/prophet_checker/sources/telegram.py` — переселення з `scripts/`
- 📋 **Scheduler** — поки без task номера; APScheduler або systemd timer
- 📋 **`src/prophet_checker/analysis/detector.py`** — productionize Task 13 winner

## OPEN QUESTION 1: Detection prefilter — обов'язковий?

**Без detector:** PredictionExtractor повертає `[]` для постів без передбачень — implicit detection. Витрачає ~17 % wasted calls на Flash Lite (cheap).

**З detector:** Для Pro Preview / two-tier strategy економить ~85 % коштів ([cost analysis](../extraction-quality-eval/2026-04-26-gemini-pro-vs-lite-cost.md), Option C).

**Decision pending:**
- Якщо лишаємось на Flash Lite single-model → detector опціональний (24% saving)
- Якщо two-tier (Flash detect → Pro extract) → detector **обов'язковий**

## OPEN QUESTION 2: яка модель для detection?

Task 13 winner = Flash Lite (F1 = 0.848). Кандидат: чи може **та сама** модель бути одночасно detector AND extractor? Один LLM call повертає `[]` коли YES/NO=NO — це натуральна детекція без окремого call.

Trade-off:
- Single call → simple, але кожен пост платить full extraction-prompt cost
- Two calls (detect cheap → extract на YES only) → складніше, але дешевше при дорогому extractor

---

## Cross-references

- Verification subflow (separate doc): [`../verifier-v2/2026-04-29-verification-cycle.md`](../verifier-v2/2026-04-29-verification-cycle.md)
- RAG subflow: [`2026-04-26-flow-production-rag.md`](2026-04-26-flow-production-rag.md)
- Idle components inventory: [`2026-04-26-idle-components.md`](2026-04-26-idle-components.md)
- Detection eval (Task 13): [`2026-04-26-flow-3-detection-eval.md`](2026-04-26-flow-3-detection-eval.md)
- Master plan task list: [`../plan/2026-04-08-prophet-checker-plan.md`](../plan/2026-04-08-prophet-checker-plan.md)
- Index: [`2026-04-26-architecture-current.md`](2026-04-26-architecture-current.md)
