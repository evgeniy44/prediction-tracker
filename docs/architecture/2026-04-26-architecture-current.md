# Prediction Tracker — Architecture (current state, focus on data flows)

**Дата:** 2026-04-26
**Status:** Living document — оновлювати при кожній зміні pipeline
**Supersedes data flow sections of:** [`2026-04-07-prophet-checker-design.md`](2026-04-07-prophet-checker-design.md) (original design — лишається як historical reference for module boundaries + AWS topology)

Цей документ фіксує **реальний** стан архітектури станом на 26 квітня 2026. Original design зосереджений на модулях і схемі БД; цей фокус — на потоках даних (5 окремих pipeline-ів), які запущені або заплановані.

---

## Changelog vs original design (2026-04-07 → 2026-04-26)

| Зміна | Статус | Причина |
|-------|--------|---------|
| YouTube collector | ❌ removed | MVP trimmed to Telegram-only (Task 11 cut 2026-04-20) |
| Detection eval pipeline (YES/NO classifier benchmark) | NEW ✅ | Task 13 — emergent потреба після виявлення проблем з extraction quality |
| Extraction quality eval (LLM-as-judge) | NEW ✅ | Task 13.5 — emergent після Task 13 |
| Gold annotation (130 manually-labeled posts) | NEW ✅ | Task 12 — необхідна основа для evals |
| Two-tier model strategy (Flash Lite for sourcing, Pro Preview for precision filter) | NEW (open question) 🚧 | Output Task 13.5 — see [`2026-04-26-gemini-pro-vs-lite-cost.md`](../extraction-quality-eval/2026-04-26-gemini-pro-vs-lite-cost.md) |
| `src/sources/` module (TelegramCollector, NewsCollector) | 📋 still planned | Сирий збір живе в `scripts/collect_telegram_posts.py`; адаптери в `src/` чекають Task 21 |
| `src/bot/` Telegram handlers | 📋 still planned | Без змін vs original — chat-frontend Phase 2 |
| `src/ingestion/` orchestrator | 📋 still planned | Task 15 — наступний крок після Task 13.5 closeout |
| `src/prophet_checker/{config, llm, models, storage, analysis}/` | ✅ implemented | 88 проходячих unit-тестів |

---

## Module inventory

| Шлях | Стан | Що містить |
|------|------|-----------|
| `src/prophet_checker/config.py` | ✅ | Pydantic Settings — `.env` → typed config |
| `src/prophet_checker/models/{domain,db}.py` | ✅ | Pydantic domain + SQLAlchemy ORM |
| `src/prophet_checker/storage/{interfaces,postgres}.py` | ✅ | Protocol + Postgres impl: 4 repositories (Person, Source, Prediction, VectorStore) |
| `src/prophet_checker/llm/{client,prompts}.py` | ✅ | LiteLLM-backed client; extraction/verification/RAG prompt templates |
| `src/prophet_checker/analysis/{extractor,verifier}.py` | ✅ | PredictionExtractor + PredictionVerifier (idle — no caller orchestrates) |
| `src/prophet_checker/sources/` | 📋 | Заплановано Task 21 — TelegramCollector + NewsCollector як адаптери з єдиним інтерфейсом |
| `src/prophet_checker/ingestion.py` | 📋 | Заплановано Task 15 — оркеструє collect→extract→save→verify |
| `src/prophet_checker/bot/` | 📋 | Заплановано пізніше — Telegram handlers + chat flow |
| `src/prophet_checker/__main__.py` (FastAPI app) | 📋 | Заплановано Task 16 |
| `scripts/collect_telegram_posts.py` | 🚧 working script | Не модуль; це one-off який пише в `data/<channel>/all.json`. Майбутнє переселення в `src/sources/telegram.py` (Task 21). |
| `scripts/evaluate_detection.py` | ✅ working script | Task 13 detection benchmark |
| `scripts/extraction_quality_eval.py` + `extraction_judge_prompts.py` | ✅ working scripts | Task 13.5 LLM-as-judge eval (3-stage) |
| `tests/` (88 tests) | ✅ | 60 detection + 28 extraction quality eval; production-class тести в analysis/llm/storage |

---

## Active data flows

5 окремих контурів даних. Перші 4 запущені; п'ятий — components built but no orchestrator yet.

### Flow 1: Telegram collection ✅ implemented

**Тригер:** ручний (одноразово per канал; повторно при додаванні нових caналів).

```
Telegram API (channels via Telethon, auth via .env TELEGRAM_API_*)
        │
        ▼
collect_telegram_posts.collect_channel()  [scripts/collect_telegram_posts.py]
   ├─ filter: len(text) >= 80, year ∈ [2012, 2026]
   ├─ scan all messages from channel via iter_messages()
   └─ even-sample by year (POSTS_PER_CHANNEL=20000, random.seed=42)
        │
        ▼ writes JSON
data/<channel>/all.json
   schema: [{id: str, person_name: str, published_at: "YYYY-MM-DD", text: str}]
   examples:
     - data/arestovich/all.json — 5572 posts (latest full run)
     - data/zdanov/1.json — 1 post (legacy stub)
```

**Окремий артефакт `data/sample_posts.json`** — вручну створена multi-person вибірка (350 Арестович + 350 Гордон + 349 Подоляк = 1049 постів), використовується як вхід для evals. Створена раніше за повний run Telegram-збору; не оновлюється автоматично.

**Майбутнє переселення:** Task 21 переносить `collect_channel` в `src/sources/telegram.py:TelegramCollector` з єдиним `Source.collect()` інтерфейсом. Output буде писатись через `SourceRepository.save_document()` в Postgres замість JSON-файлу.

---

### Flow 2: Gold annotation ✅ implemented

**Тригер:** ручний (1-2 рази; розширюється коли треба покрити нові edge cases).

```
data/sample_posts.json (1049 posts: Арестович+Гордон+Подоляк)
        │
        ▼ людина читає по черзі, керується guidelines
docs/annotation-guidelines.md (rubric: YES/NO + 7 anti-patterns)
        │
        ▼ ручний JSON-вивід
data/gold_labels.json
   schema: [{id: str, has_prediction: bool}]
   counts: 130 entries — 97 Арестович + 16 Подоляк + 17 інші
                          з них 15 YES Арестович, 82 NO Арестович
```

**Жодного скрипта-помічника** в репозиторії немає — gold-labels.json створювався вручну (terminal interaction в окремих сесіях, фіксувався як commit). Послідовність: Task 12 початково на 50 постах (commit `428aea4`), розширення до 130 (commit `a992e0f`).

Цей артефакт — фундамент для двох eval-flows нижче.

---

### Flow 3: Detection eval (Task 13) ✅ implemented

**Тригер:** ручний (запускається при появі нового кандидата на production-модель).

```
data/gold_labels.json + data/sample_posts.json
        │
        ▼ inner-join по id → ~130 анотованих постів
evaluate_detection.run_evaluation_for_model()  [scripts/evaluate_detection.py]
   ├─ для кожної моделі × промпт-версії:
   ├─   для кожного посту: LLM call → бінарний YES/NO
   ├─   compare with gold → обчислити TP/FP/FN/TN
   └─ aggregate → P/R/F1 + per-error-bucket breakdown
        │
        ▼ writes 1 JSON per (model, prompt-version)
outputs/detection_eval/detection_results_<provider>_<model>[_v1_baseline].json
   schema: {model_id, prompt_version, n_pos, n_neg, tp, fp, fn, tn,
            precision, recall, f1, errors: [{post_id, label, predicted, ...}]}
   actual count: 10 файлів — 5 моделей × 2 prompt versions

Models tested: claude-haiku-4-5, deepseek-chat,
               gemini-3.1-flash-lite-preview, gpt-5-mini, llama-3.3-70b
Prompt versions: v1 (baseline) + v2 (refined)

WINNER (production decision): gemini/gemini-3.1-flash-lite-preview
  F1 = 0.848 (precision 0.79, recall 0.92)
```

**Передбачення наступного запуску:** додаються новi моделі (наприклад gemini-3.1-pro, claude-opus-4-6). Кожен запуск перетирає `detection_results_<model>.json` своєю версією, але v1_baseline залишається як reference точка.

---

### Flow 4: Extraction quality eval (Task 13.5) ✅ implemented

**Тригер:** ручний (запускається при зміні prompt'у чи додаванні моделі-кандидата).

3-стадійний pipeline з LLM-as-judge.

```
                ┌─ data/gold_labels.json (130 entries)
                ├─ data/sample_posts.json (1049 posts, --gold-only filters до 97 Arestovich)
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 1: extraction                                                │
│   extraction_quality_eval.run_stage1_extraction()                  │
│     ├─ for each (model, post): PredictionExtractor.extract()      │
│     │    (REUSES src/prophet_checker/analysis/extractor.py!)       │
│     ├─ rate-limit: per-model concurrency + min_call_interval       │
│     └─ merge-mode: новий run з тим же model_id перетирає, інші    │
│                    моделі зберігаються                             │
│                                                                    │
│   ▼ writes (or merges)                                             │
│   outputs/extraction_eval/extraction_outputs.json                  │
│     schema: {                                                      │
│       metadata: {timestamp, dataset_size, extractors[], author},   │
│       extractions: {model_id: {post_id: [claim_dict]}},            │
│       errors: {model_id: {post_id: error_str}}                     │
│     }                                                              │
└──────────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 2: judge                                                     │
│   extraction_quality_eval.run_stage2_judge()                       │
│     ├─ judge model: anthropic/claude-opus-4-6                      │
│     ├─ for each (extracted_claim, post_text):                      │
│     │    LLM-as-judge → 6-value verdict per claim                  │
│     │      verdicts: exact_match / faithful_paraphrase /           │
│     │                valid_but_metadata_error / not_a_prediction / │
│     │                truncated / hallucination                     │
│     ├─ judge ALSO produces missed_predictions list (anchor: same   │
│     │    rubric applied to both extracted AND missed)              │
│     ├─ extractors_filter — incremental mode: judge only new model  │
│     │    додав і змерджив зі старими judgements                    │
│     └─ posts filter (--gold-only) → ~97 Arestovich posts           │
│                                                                    │
│   ▼ writes                                                         │
│   outputs/extraction_eval/extraction_judgements.json               │
│     schema: {                                                      │
│       metadata: {timestamp, judge, source_extractions},            │
│       judgements: {model_id: {post_id: {                           │
│         per_claim: [{claim_text, verdict, reasoning}],             │
│         missed_predictions: [{text_excerpt, why_valid}],           │
│         parse_error: str | null,                                   │
│       }}}                                                          │
│     }                                                              │
└──────────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 3: aggregate                                                 │
│   extraction_quality_eval.run_stage3_aggregate()                   │
│     ├─ verdict ordinal mapping: exact/faithful=3, metadata=2,     │
│     │   not_pred/truncated=1, hallucination=0                      │
│     ├─ per-model: avg_quality_score, hallucination_rate,           │
│     │   missed_count, gold_agreement matrix                        │
│     └─ exclude parse_errors from gold_agreement                    │
│                                                                    │
│   ▼ writes                                                         │
│   outputs/extraction_eval/extraction_eval_report.json              │
│     schema: {                                                      │
│       metadata: {timestamp, source_judgements, source_gold},       │
│       per_model: {model_id: {total_claims, verdict_distribution,  │
│         avg_quality_score, hallucination_rate,                     │
│         missed_predictions_count, gold_agreement: {                │
│           gold_YES_with_valid_extraction,                          │
│           gold_YES_no_valid_extraction,                            │
│           gold_NO_with_extractions_labeled_valid,                  │
│           gold_NO_without_valid_extractions                        │
│       }}}                                                          │
│     }                                                              │
└──────────────────────────────────────────────────────────────────┘

Models tested (latest run, 2026-04-26):
  gemini-3.1-pro-preview          avg=2.30 precision=65% recall=60% [paid Tier 1]
  gemini-3.1-flash-lite-preview   avg=2.03 precision=51% recall=73% [free tier OK]
  deepseek-chat                   avg=1.88 precision=44% recall=60%
  claude-sonnet-4-6               avg=1.67 precision=33% recall= 7% [катастрофа]

PRODUCTION DECISION (поки що): gemini/gemini-3.1-flash-lite-preview
  — кращий recall + 33× дешевше за Pro Preview
  — see docs/2026-04-26-gemini-pro-vs-lite-cost.md
```

**Артефакти позаплановані**: `outputs/extraction_eval/gemini_missed_predictions.json` — manual analysis dump для глибшого аналізу того що Gemini-моделі пропустили (one-off).

---

### Flow 5a: Idle production components 🚧 components built, NOT orchestrated

Просто інвентар написаних класів. Між ними немає runtime-зв'язків поки що — нікого, хто би їх викликав end-to-end.

```
┌─ src/prophet_checker/llm/client.py:LLMClient ─────────────────────┐
│   .complete(prompt, system) -> str                                │
│   .embed(text) -> list[float] (1536-dim, OpenAI text-embedding-3) │
│   provider-agnostic via LiteLLM                                   │
└────────────────────────────────────────────────────────────────────┘

┌─ src/prophet_checker/analysis/extractor.py:PredictionExtractor ───┐
│   .extract(text, person_id, document_id, person_name,             │
│            published_date) -> list[Prediction]                    │
│   uses: LLMClient + EXTRACTION_SYSTEM prompt                      │
│   ALSO USED BY: extraction_quality_eval Stage 1 (eval flow)       │
└────────────────────────────────────────────────────────────────────┘

┌─ src/prophet_checker/analysis/verifier.py:PredictionVerifier ─────┐
│   .verify(prediction) -> Prediction (status/confidence updated)   │
│   uses: LLMClient + VERIFICATION_SYSTEM prompt                    │
│   threshold: confidence < 0.6 → status=UNRESOLVED                 │
└────────────────────────────────────────────────────────────────────┘

┌─ src/prophet_checker/storage/postgres.py: 4 repositories ─────────┐
│   PostgresPersonRepository                                        │
│     .save / .get_by_id / .list_all                                │
│   PostgresSourceRepository                                        │
│     .save_person_source / .get_person_sources                     │
│     .save_document / .get_document_by_url                         │
│     .get_unprocessed_documents / .get_last_collected_at           │
│   PostgresPredictionRepository                                    │
│     .save / .get_by_person / .get_unverified / .update            │
│   PostgresVectorStore (pgvector)                                  │
│     .store_embedding / .search_similar                            │
└────────────────────────────────────────────────────────────────────┘

Domain models (Pydantic, src/prophet_checker/models/domain.py):
  Person (id, name, description, created_at)
  PersonSource (id, person_id, source_type, source_identifier, enabled)
  RawDocument (id, person_id, source_type, url, published_at, raw_text,
               language, collected_at)
  Prediction (id, person_id, document_id, claim_text, prediction_date,
              target_date, topic, status, confidence, evidence_url,
              evidence_text, verified_at, embedding)
  Enums: SourceType (TELEGRAM, NEWS, ...), PredictionStatus (CONFIRMED,
         REFUTED, UNRESOLVED)
```

---

### Flow 5b: Production extraction + verification + RAG 📋 designed only

Цільовий потік даних після Task 15-16 (orchestrator + FastAPI). Box з 📋 — те що ще не написано.

```
┌────────────────── INGESTION (periodic, scheduler) ─────────────────┐
│                                                                     │
│   📋 scheduler (cron-like, e.g. APScheduler)                        │
│        │ trigger every N hours                                      │
│        ▼                                                            │
│   📋 src/prophet_checker/ingestion.py:IngestionOrchestrator         │
│        │                                                            │
│        ▼ for each enabled person+source pair                        │
│   PostgresSourceRepository.get_person_sources()                     │
│        │ where enabled=True                                         │
│        ▼                                                            │
│   📋 src/prophet_checker/sources/<type>.py:Source.collect()         │
│        │   collects new docs since                                  │
│        │   PostgresSourceRepository.get_last_collected_at()         │
│        ▼                                                            │
│   PostgresSourceRepository.save_document(RawDocument)               │
│        │   (deduplication by URL handled here)                      │
│        ▼                                                            │
│   PostgresSourceRepository.get_unprocessed_documents()              │
│        │                                                            │
│        ▼ for each unprocessed document                              │
│   📋 src/prophet_checker/analysis/detector.py:PredictionDetector    │
│        │   .has_prediction(text) -> bool                            │
│        │   uses: cheap model (Flash Lite, F1=0.848 from Task 13)    │
│        │   purpose: skip 80%+ of posts that contain no predictions │
│        │   STATUS: Task 13 produced only an eval script,            │
│        │           no production class yet                          │
│        ▼ (only if has_prediction == True)                           │
│   src/prophet_checker/analysis/extractor.py:PredictionExtractor     │
│        │   .extract(doc.text, ...) -> list[Prediction]              │
│        │   ↑ also generates embedding via LLMClient.embed()         │
│        ▼                                                            │
│   PostgresPredictionRepository.save(prediction)                     │
│   PostgresVectorStore.store_embedding(pred_id, embedding)           │
│                                                                     │
│   📋 OPEN QUESTION 1: do we need explicit detector at all?          │
│       Without it: PredictionExtractor returns [] for posts without  │
│       predictions — implicit detection. Costs ~17% wasted calls     │
│       on Flash Lite (cheap). But for Pro Preview / two-tier         │
│       strategy, explicit Detector saves ~85% (see                   │
│       docs/2026-04-26-gemini-pro-vs-lite-cost.md, "Option C").     │
│   📋 OPEN QUESTION 2: which model for detection?                    │
│       Task 13 winner = Flash Lite (F1=0.848). Could same model      │
│       serve both detection and extraction (single LLM call          │
│       returning empty array on NO)?                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼

┌──────────────── VERIFICATION (deferred, async) ───────────────────┐
│                                                                    │
│   📋 scheduler (separate cadence, e.g. daily)                      │
│        │                                                           │
│        ▼                                                           │
│   PostgresPredictionRepository.get_unverified()                    │
│        │   CURRENTLY: WHERE status=UNRESOLVED AND verified_at IS    │
│        │              NULL — no time gate at all                    │
│        │   🚨 BUG: returns predictions whose event hasn't happened  │
│        │       yet (e.g. "Війна закінчиться у 2027" verified today  │
│        │       — meaningless)                                       │
│        ▼ for each unverified prediction                             │
│   src/prophet_checker/analysis/verifier.py:PredictionVerifier      │
│        │   .verify(pred) → updated Prediction with                 │
│        │   {status, confidence, evidence_url, evidence_text,       │
│        │    verified_at}                                           │
│        ▼                                                           │
│   PostgresPredictionRepository.update(pred)                        │
│                                                                    │
│   🚨 OPEN QUESTION 1: WHEN is a prediction eligible for             │
│      verification? Critical because target_date is NULL in         │
│      ~70-90% of extracted claims (LLMs rarely produce a deadline). │
│      Candidate policies (needs separate brainstorm):                │
│        • Strict: target_date IS NOT NULL AND target_date < NOW()    │
│          (excludes 70-90% of corpus — likely too restrictive)      │
│        • Soft fallback: + prediction_date + Δ for null cases       │
│        • LLM-as-gatekeeper: per-prediction "is this verifiable     │
│          now?" call before each verify attempt                      │
│        • Multi-tier: target_date defined → strict; null → re-      │
│          extract from text; vague → manual queue                    │
│      No decision made yet. See followup brainstorm.                 │
│                                                                    │
│   📋 OPEN QUESTION 2: де брати news для верифікації?                │
│       — окремий NewsCollector (Task 22)?                           │
│       — web search в LLMClient (LiteLLM web_search_options)?        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘


┌──────────────── RAG QUERY (synchronous, on-demand) ───────────────┐
│                                                                    │
│   📋 User question (Telegram bot or HTTP API)                      │
│        │                                                           │
│        ▼                                                           │
│   📋 src/prophet_checker/bot/handlers.py (or FastAPI endpoint)     │
│        │                                                           │
│        ▼                                                           │
│   LLMClient.embed(query) → 1536-dim vector                         │
│        │                                                           │
│        ▼                                                           │
│   PostgresVectorStore.search_similar(embedding, limit=10)          │
│        │   → list[prediction_id]                                   │
│        ▼                                                           │
│   PostgresPredictionRepository.get_by_ids(ids)                     │
│        │                                                           │
│        ▼                                                           │
│   LLMClient.complete(query + relevant_predictions, RAG_SYSTEM)     │
│        │                                                           │
│        ▼                                                           │
│   📋 response → Telegram / HTTP                                    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**Список обов'язкових до Flow 5b gap-fillers:**
- 📋 Task 15: `src/prophet_checker/ingestion.py` — оркестратор всіх стадій
- 📋 Task 16: FastAPI app entry (`__main__.py`) — exposes orchestrator + RAG
- 📋 Task 17-19: Docker + Alembic migration + integration smoke test
- 📋 Task 21: `src/prophet_checker/sources/telegram.py` — переселення з `scripts/`
- 📋 Task 22: `src/prophet_checker/sources/news.py` — для verification
- 📋 Bot module + scheduler (поки без task номерів)
- 🚨 **Verification trigger policy** — окремий followup brainstorm.
  Поточний `get_unverified()` ігнорує час; потрібно вирішити ЯК і КОЛИ
  predictions стають eligible (target_date null у 70-90% claims).
- 📋 **`src/prophet_checker/analysis/detector.py`** — productionize Task 13
  Detection winner (Flash Lite) як explicit pipeline stage. Опціональний
  для single-Flash-Lite extraction; обов'язковий для two-tier (Flash Lite
  detect → Pro Preview extract).

---

## Shared components (eval ↔ production)

Чому eval-flows важливі архітектурно: вони **не паралельний контур**, а **той самий** код в інших режимах.

| Компонент | Eval flow використовує | Production flow використовує |
|-----------|------------------------|------------------------------|
| `LLMClient` (LiteLLM) | Stage 1 extraction calls, Stage 2 judge calls | PredictionExtractor, PredictionVerifier, RAG |
| `EXTRACTION_SYSTEM` prompt | Stage 1 (`scripts/extraction_quality_eval.py` reuses `src/prophet_checker/llm/prompts.py`) | PredictionExtractor (production) |
| `PredictionExtractor` class | Stage 1 (`scripts/extraction_quality_eval.py` імпортує з src) | Майбутній orchestrator |
| Pydantic domain models | Eval scripts читають gold/sample у тих же shapes | Postgres repos через `domain_to_*_db()` |
| `CONCURRENCY_OVERRIDES`, `MIN_CALL_INTERVAL_SECONDS` | Per-model rate-limit для eval-burst | Майбутній orchestrator теж буде поважати |

**Імплікація:** покращення в одному місці автоматично проявляються в обох контурах. Наприклад: коли в Task 13.5 додали criterion 4 (substantiveness) у `EXTRACTION_SYSTEM`, тепер і eval-прогон, і майбутня production-екстракція використовують ту саму, покращену версію.

**Антипатерн якого уникаємо:** окремі prompt'и для eval і production. Це б призвело до випадку де "eval каже модель добра", а в production вона працює гірше (різні prompt'и → різна якість).

---

## What's next

Безпосередній наступний крок — **Task 15: Ingestion Orchestrator**. Це перший gap-filler у Flow 5b. Без нього всі написані src/-класи лишаються мертвим вантажем.

**Найближчі 4 задачі (порядок):**
1. **Task 15** — `IngestionOrchestrator`: збирає на цикл `collect → extract → save`. Все ще без verification (deferred). Тестується через mock-source.
2. **Task 16** — FastAPI entry: HTTP-trigger для orchestrator (поки без bot).
3. **Task 17-19** — Docker Compose, Alembic міграція на справжню Postgres, integration smoke test.
4. **Task 21** — `src/sources/telegram.py`: переселення `scripts/collect_telegram_posts.py` в src/-модуль через `Source.collect()` інтерфейс.

**Open architectural questions** (не вирішено в цьому doc):
- 🚨 **Verification trigger policy** — критичне. Коли prediction стає eligible
  для verification? `target_date` null у 70-90% claims. 5 кандидатів-політик
  (strict / soft fallback / LLM-gatekeeper / multi-tier / open-ended periodic).
  Без цього `PredictionVerifier` фактично не можна включити в продукт. Окремий
  brainstorm перед Task 15.
- Detection prefilter перед extraction у Flow 5b? Може зекономити ~85 % коштів
  при two-tier strategy (Pro Preview як second-stage). Спроектувати окремо
  при Task 15.
- Two-stage extraction: Flash Lite (sourcing) + Pro Preview (precision filter)?
  Hypothesized в cost-comparison doc, потребує proof-of-concept на ~50 постах.
- Чи додавати eval-loop у production як continuous quality monitoring?
  Зараз eval — manual one-off; майбутнє — можливо щоденний sample-based health
  check.

Ці питання — кандидати на наступний architecture refresh (Option B/C у початковому brainstormі).

---

## Cross-references

- Original design (модулі + AWS topology): [`2026-04-07-prophet-checker-design.md`](2026-04-07-prophet-checker-design.md)
- Master plan + task statuses: [`2026-04-08-prophet-checker-plan.md`](../plan/2026-04-08-prophet-checker-plan.md)
- Annotation rubric: [`annotation-guidelines.md`](../annotation/annotation-guidelines.md)
- Extraction eval design: [`2026-04-21-extraction-quality-eval-design.md`](../extraction-quality-eval/2026-04-21-extraction-quality-eval-design.md)
- Extraction eval implementation plan: [`2026-04-21-extraction-quality-eval-plan.md`](../extraction-quality-eval/2026-04-21-extraction-quality-eval-plan.md)
- Cost comparison Flash Lite vs Pro Preview: [`2026-04-26-gemini-pro-vs-lite-cost.md`](../extraction-quality-eval/2026-04-26-gemini-pro-vs-lite-cost.md)
- Per-post extraction reports: [`2026-04-26-extraction-consolidated-report.md`](../extraction-quality-eval/2026-04-26-extraction-consolidated-report.md)
- Scripts layout & scenarios: [`../scripts/README.md`](../../scripts/README.md)
