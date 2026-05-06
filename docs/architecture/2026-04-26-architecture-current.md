# Prediction Tracker — Architecture (current state)

**Дата:** 2026-04-26
**Status:** Living document — оновлювати при кожній зміні pipeline

Цей документ — **index** для архітектури станом на 26 квітня 2026. Кожен data flow живе в окремому файлі (детальна Mermaid-діаграма + schema + open questions). Тут — module inventory + table-of-contents 7 потоків + shared components + what's next.

---

## Changelog vs original design (2026-04-07 → 2026-04-29)

| Зміна | Статус | Причина |
|-------|--------|---------|
| YouTube collector | ❌ removed | MVP trimmed to Telegram-only (Task 11 cut 2026-04-20) |
| Detection eval pipeline (YES/NO classifier benchmark) | NEW ✅ | Task 13 — emergent потреба після виявлення проблем з extraction quality |
| Extraction quality eval (LLM-as-judge) | NEW ✅ | Task 13.5 — emergent після Task 13 |
| Gold annotation (130 manually-labeled posts) | NEW ✅ | Task 12 — необхідна основа для evals |
| Verifier v2 (4-status + retry-loop policy) | NEW ✅ designed | Resolves target_date=null у 70-90 % claims, see [`../verifier-v2/`](../verifier-v2/) |
| Two-tier model strategy (Flash Lite + Pro Preview) | 🚧 open | Task 13.5 output, see [`cost-comparison`](../extraction-quality-eval/2026-04-26-gemini-pro-vs-lite-cost.md) |
| `src/prophet_checker/sources/` module (TelegramSource) | ✅ done 2026-04-29 | Task 21 done — `TelegramSource` реалізовано; `scripts/collect_telegram_posts.py` видалено. NewsCollector не в scope MVP. |
| `src/bot/` Telegram handlers | 📋 still planned | Chat-frontend Phase 2 |
| `src/ingestion/` orchestrator | 📋 still planned | Task 15 — наступний крок |
| `src/prophet_checker/{config, llm, models, storage, analysis}/` | ✅ implemented | 88 проходячих unit-тестів |

---

## Module inventory

| Шлях | Стан | Що містить |
|------|------|-----------|
| `src/prophet_checker/config.py` | ✅ | Pydantic Settings — `.env` → typed config |
| `src/prophet_checker/models/{domain,db}.py` | ✅ | Pydantic domain + SQLAlchemy ORM |
| `src/prophet_checker/storage/{interfaces,postgres}.py` | ✅ | Protocol + Postgres impl: 4 repositories (Person, Source, Prediction, VectorStore) |
| `src/prophet_checker/llm/{client,embedding,prompts}.py` | ✅ | LiteLLM-backed clients (LLMClient = completion, EmbeddingClient = embedding — split 2026-05-01); extraction/verification/RAG prompt templates |
| `src/prophet_checker/analysis/{extractor,verifier}.py` | ✅ | PredictionExtractor + PredictionVerifier (orchestrator wires extractor since Task 15) |
| `src/prophet_checker/sources/{base,telegram,mock}.py` | ✅ | Source Protocol + TelegramSource (Task 21) + MockSource (Task 15 testing) |
| `src/prophet_checker/ingestion/{orchestrator,report}.py` | ✅ | IngestionOrchestrator + CycleReport/ChannelReport (Task 15 done 2026-05-01) |
| `src/prophet_checker/{app,factory,__main__}.py` (FastAPI) | ✅ | FastAPI app + build_orchestrator wiring + uvicorn entry (Task 16 done 2026-05-05) |
| `src/prophet_checker/bot/` | 📋 | Заплановано пізніше |
| `scripts/evaluate_detection.py` | ✅ working script | Task 13 detection benchmark |
| `scripts/extraction_quality_eval.py` + `extraction_judge_prompts.py` | ✅ working scripts | Task 13.5 LLM-as-judge eval (3-stage) |
| `tests/` (122 tests) | ✅ | detection + extraction quality eval + sources + analysis + llm (client + embedding) + storage + ingestion (orchestrator + integration) + app/factory/config (FastAPI); production-class тести скрізь |

---

## Active data flows (7 окремих docs)

Перші 4 запущені; решта — components built but not orchestrated.

| Flow | Status | Doc |
|------|--------|-----|
| 1 — Telegram collection | ✅ implemented (script) | [`flow-1-telegram-collection.md`](2026-04-26-flow-1-telegram-collection.md) |
| 2 — Gold annotation | ✅ implemented (manual) | [`flow-2-gold-annotation.md`](2026-04-26-flow-2-gold-annotation.md) |
| 3 — Detection eval (Task 13) | ✅ implemented | [`flow-3-detection-eval.md`](2026-04-26-flow-3-detection-eval.md) |
| 4 — Extraction quality eval (Task 13.5) | ✅ implemented | [`flow-4-extraction-quality-eval.md`](2026-04-26-flow-4-extraction-quality-eval.md) |
| 5a — Idle production components | 🚧 built, not orchestrated | [`idle-components.md`](2026-04-26-idle-components.md) |
| 5b — Production ingestion | 📋 designed only | [`flow-production-ingestion.md`](2026-04-26-flow-production-ingestion.md) |
| 5c — Production verification | ✅ designed (verifier-v2) | [`../verifier-v2/2026-04-29-verification-cycle.md`](../verifier-v2/2026-04-29-verification-cycle.md) |
| 5d — Production RAG query | 📋 designed only | [`flow-production-rag.md`](2026-04-26-flow-production-rag.md) |

---

## Shared components (eval ↔ production)

Чому eval-flows важливі архітектурно: вони **не паралельний контур**, а **той самий** код в інших режимах.

| Компонент | Eval flow використовує | Production flow використовує |
|-----------|------------------------|------------------------------|
| `LLMClient` (LiteLLM) | Stage 1 extraction calls, Stage 2 judge calls | PredictionExtractor, PredictionVerifier, RAG |
| `EXTRACTION_SYSTEM` prompt | Stage 1 (`scripts/extraction_quality_eval.py` reuses `src/prophet_checker/llm/prompts.py`) | PredictionExtractor (production) |
| `PredictionExtractor` class | Stage 1 (eval скрипт імпортує з src) | Майбутній orchestrator |
| Pydantic domain models | Eval scripts читають gold/sample у тих же shapes | Postgres repos через `domain_to_*_db()` |
| `CONCURRENCY_OVERRIDES`, `MIN_CALL_INTERVAL_SECONDS` | Per-model rate-limit для eval-burst | Майбутній orchestrator теж буде поважати |

**Імплікація:** покращення в одному місці автоматично проявляються в обох контурах. Наприклад: коли в Task 13.5 додали criterion 4 (substantiveness) у `EXTRACTION_SYSTEM`, тепер і eval-прогон, і майбутня production-екстракція використовують ту саму, покращену версію.

**Антипатерн якого уникаємо:** окремі prompt'и для eval і production. Це б призвело до випадку де "eval каже модель добра", а в production вона працює гірше (різні prompt'и → різна якість).

---

## What's next

Безпосередній наступний крок — **Task 15: Ingestion Orchestrator**. Це перший gap-filler у Flow 5b. Без нього всі написані src/-класи лишаються мертвим вантажем.

**Найближчі задачі (порядок):**

1. **Verifier v2 implementation** — see [`../verifier-v2/2026-04-29-verification-trigger-policy-plan.md`](../verifier-v2/2026-04-29-verification-trigger-policy-plan.md). 9 TDD tasks, ~30 tests. Self-contained — ship'аємо ДО Task 15.
2. **Task 15** — `IngestionOrchestrator`: збирає на цикл `collect → extract → save`. Тестується через mock-source.
3. **Task 16** — FastAPI entry: HTTP-trigger для orchestrator (поки без bot).
4. **Task 17-19** — Docker Compose, Alembic міграція на справжню Postgres, integration smoke test.
5. **Task 21** — ✅ done 2026-04-29: `src/prophet_checker/sources/telegram.py:TelegramSource` — переселення завершено, legacy script видалено.

**Open architectural questions** (не вирішено в цьому doc):

- **Detection prefilter** перед extraction — обов'язковий для two-tier (Pro Preview as second-stage), опціональний для single Flash Lite. Спроектувати при Task 15. Деталі: [`flow-production-ingestion.md`](2026-04-26-flow-production-ingestion.md) Open Question 1.
- **Two-stage extraction**: Flash Lite (sourcing) + Pro Preview (precision filter)? Hypothesized в [cost-comparison](../extraction-quality-eval/2026-04-26-gemini-pro-vs-lite-cost.md), потребує proof-of-concept на ~50 постах.
- **Eval-loop у production як continuous quality monitoring?** Зараз eval — manual one-off; майбутнє — можливо щоденний sample-based health check.

---

## Cross-references

- Master plan + task statuses: [`../plan/2026-04-08-prophet-checker-plan.md`](../plan/2026-04-08-prophet-checker-plan.md)
- Annotation rubric: [`../annotation/annotation-guidelines.md`](../annotation/annotation-guidelines.md)
- Verifier v2 docs: [`../verifier-v2/`](../verifier-v2/)
- Extraction eval docs: [`../extraction-quality-eval/`](../extraction-quality-eval/)
- Scripts layout & scenarios: [`../../scripts/README.md`](../../scripts/README.md)
