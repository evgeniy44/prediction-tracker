# Prediction Tracker — Progress Log

Living log: time, cost, deliverables. Оновлюється коли завершується milestone або значуща задача.
Project-wide джерело правди по статусу; per-track деталі — у `docs/<track>/README.md`.

**Останнє оновлення:** 2026-06-03

---

## Current state (snapshot 2026-06-03)

| Metric | Value |
|--------|-------|
| Календарний час від старту | ~56 днів (2026-04-08 → 2026-06-03) |
| Commits | 208 |
| Tests passing | 198 |
| Tasks completed | M1 (5/5) + M2 (5/5) + M2.5 (eval/data) + Ingestion→production track + Verifier-v2 track (19.5→19.9 + Task 20) |
| Tasks in flight | — |
| Tasks queued | Recheck-луп, AWS deploy, GitHub Actions CI |
| AWS cost | $0 (not deployed yet) |

**Активний фокус:** Verifier-v2 track завершено по first-pass (19.5→20). `Verifier` зв'язаний з БД
через `VerificationOrchestrator`. Далі — recheck-луп для `premature` або push/deploy.

> **Нумерація:** verifier-v2 track має власну внутрішню нумерацію (19.5/19.7/19.8/19.9/20).
> Її "Task 20" (orchestrator) — це verifier-track задача, не плутати з ранньою backlog-задачею
> "GitHub Actions CI".

---

## Phase 0–2: Foundation + AI Pipeline (Tasks 0–9) ✅ COMPLETE

- **M1 (0–4):** scaffold, config, Pydantic domain models, Protocol storage, SQLAlchemy ORM + Alembic. ~16 tests.
- **M2 (5–9):** Postgres storage impl, LiteLLM client, prompt templates, PredictionExtractor, PredictionVerifier v1 (згодом superseded Verifier v2). ~23 tests.

**Key decisions:** Python/FastAPI, monolith ports-and-adapters, Protocol storage + fakes, LiteLLM, PostgreSQL + pgvector.

---

## Phase 3 / 3.5: Eval, Data & Design Refresh ✅ COMPLETE

- **Збір даних:** 5572 Arestovich posts (Telethon), 130 gold detection labels.
- **Task 13 — Detection eval:** 5 моделей × 2 prompts → **Winner: Gemini 3.1 Flash Lite** (F1=0.848).
- **Task 13.5 — Extraction quality eval:** 3-stage LLM-as-judge → **production: Flash Lite** (33× дешевше, кращий recall). Деталі: [`docs/extraction-quality-eval/`](docs/extraction-quality-eval/).
- **Design refresh:** [`docs/architecture/2026-04-26-architecture-current.md`](docs/architecture/2026-04-26-architecture-current.md) (index + 7 flow docs), Verifier-v2 spec у [`docs/verifier-v2/`](docs/verifier-v2/).
- **Ключова знахідка:** 70–90% extracted claims мають `target_date=null` → блокує v1 verifier → драйвер Verifier v2.

---

## Phase 4: Ingestion → production ✅ COMPLETE

Ingestion pipeline + FastAPI HTTP trigger працюють end-to-end (підтверджено CLAUDE.md +
[`docs/architecture/2026-04-26-architecture-current.md`](docs/architecture/2026-04-26-architecture-current.md)).

| Task | Deliverable |
|------|-------------|
| 21 — TelegramSource adapter | Telethon `Source`, oldest-first для cursor-monotonic advance |
| 15 — IngestionOrchestrator | `run_cycle()` → collect → extract → persist → `CycleReport` |
| 16 — FastAPI app entry | `GET /health` + `POST /ingest/run`, composition root у `factory.py` |
| 17 — Docker Compose | Postgres + pgvector контейнер, local dev workflow |
| 18 — Alembic on real Postgres | міграції застосовуються на реальній БД |
| 19 — Integration smoke | `scripts/ingestion/integration_smoke.py` (real Postgres + Telegram + LLM) |

Специфікації: [`docs/ingestion-to-aws/`](docs/ingestion-to-aws/).

---

## Phase 5: Verifier-v2 track 🟢 MOSTLY COMPLETE

Повний статус + mermaid: [`docs/verification-track/README.md`](docs/verification-track/README.md).

| Sub-task | Статус | Результат |
|----------|--------|-----------|
| 19.5 — V2 schema + prompts + parser | ✅ | 4-status (confirmed/refuted/unresolved/premature) + strength + 6 urgency-полів |
| PredictionValue extension | ✅ | 8-й output (importance/resonance) |
| 19.7a — Gold v1 | ✅ | 35 Arestovich predictions, V2 schema |
| 19.8a–d — context→situation | ✅ | `situation` (model-paraphrase, presence-validated) замінив verbatim context |
| 19.8b — fresh gold | ✅ | 32 claims з situation (`scripts/data/verification_gold_labels.json`) |
| 19.7b — model eval | ✅ | 9 моделей × 32 gold → **production model = Gemini Flash Lite**. Сага тюнінгу V2→V7 + split: [`docs/verification-track/19-7b-verification-eval/prompt-history.md`](docs/verification-track/19-7b-verification-eval/prompt-history.md) |
| 19.9 — Split Verifier (2-call) | ✅ | verdict + assessment виклики розривають single-call tradeoff. **Flash Lite: firm-status 0.833 / strength 0.719 / value 0.812.** `Verifier` у `analysis/verifier.py`. Commits `de6afd4`→`a670158` |
| 20 — VerificationOrchestrator (first-pass) | ✅ | Pull get_unverified → `Verifier` → write-back з urgency-полями. `verification/` пакет + PREMATURE + update() V2 + factory + CLI. Commits `a2933a0`→`d329408`, 190→198 tests |

**Допоміжне:** 3-стадійний pipeline `extraction/sample_posts → extraction/run_extraction → verification/run_verification`
для ручного рев'ю якості (outputs у `scripts/outputs/pipeline_run/`).

---

## Phase 6: AWS deploy + CI 📋 QUEUED

| Task | Статус |
|------|--------|
| 23 — AWS RDS PostgreSQL + pgvector | 📋 |
| 24 — AWS EC2 + Docker deploy | 📋 |
| 20 (master-plan) — GitHub Actions CI | 📋 (опціонально, після deploy) |

---

## Phase 7: Future (post-MVP)

1. **Verifier recheck-луп** — повторна перевірка `premature` за `next_check_at` до `max_horizon` (urgency-поля вже пишуться у Task 20).
2. Detection prefilter (`PredictionDetector`) — якщо two-tier.
3. Telegram bot frontend + RAG query endpoint.
4. News collector (Task 22) — для verifier evidence.
5. Continuous eval-loop (production quality monitoring).

---

## Cost log (approximate)

| Категорія | Cost |
|-----------|------|
| LLM API (eval runs: detection + extraction quality + verification + prompt-tuning сага) | ~$25–35 |
| Claude Code dev (numerous Opus sessions) | ~$50–250 (estimated) |
| AWS | $0 |
| GitHub | $0 (public) |
| **Total to date** | **~$75–285** |

---

## Notes

- **Velocity** ~199 commits / ~56 днів ≈ 3.5 commits/день calendar; pet-project pace.
- **Pivot:** після ingestion→production завершився, фокус перейшов на Verifier v2 (раніше deferred) — він виявився найбільш ітерованою областю продукту.
- **Детермінований eval-інсайт (19.9):** temperature=0 для Flash Lite повністю детермінований → prompt-тюнінг ведеться як точна наука, без sampling-noise. Single-call має інхерентний tradeoff (strength-fix псує status); декомпозиція на 2 виклики його розриває.
- **RAG retrieval v1 (2026-06-21):** retrieval eval-харнес готовий (`scripts/retrieval/`, Tasks 1–10, 27 тестів; design+plan у `docs/retrieval-eval/`). **РІШЕННЯ:** робоча конфігурація retrieval зафіксована вольовим вибором — embedding = `text-embedding-3-small`, репрезентація = **`claim+situation`** (1536-dim = поточна колонка `predictions.embedding`, без міграції). Мультимодельне порівняння (MMTEB-screening + sweep) **PARKED** — харнес лишається для майбутнього прогону, не загублено. Прокинуто в прод-інжест (`embedding_text()` у `analysis/`, оркестратор ембедить claim+situation) + `embeddings_enabled=True` + backfill-скрипт.
- **RAG query serving (2026-06-22):** `POST /query` готовий end-to-end. `QueryOrchestrator.search` (embed → `search_similar`(scored) → `get_by_ids` → `QueryResult`), **retrieval-only (gen-ready)**, top-k + `distance` без порога. Нові доменні моделі `VectorMatch`/`RetrievedPrediction`/`QueryResult`; `get_by_ids` (order-preserving); endpoint + lifespan-wiring. Design+plan: [`docs/query-serving/`](docs/query-serving/). **Фікс:** `search_similar` фільтрує `embedding IS NULL` (інакше `cosine_distance(NULL)`→`distance=None`→краш на не-backfill'нутому корпусі). Backfill ідемпотентний (`is_embedding_present` → skip-already-embedded). Уся сюїта **270 тестів**. **Наступне:** прогнати backfill на проді (наразі всі 4046 прогнозів `embedding IS NULL`) + smoke `/query`; далі **v1.5 генерація** (`answer(QueryResult)` + citation/refusal/faithfulness-eval) і Telegram-бот.
