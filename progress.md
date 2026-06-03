# Prediction Tracker — Progress Log

Living log: time, cost, deliverables. Оновлюється коли завершується milestone або значуща задача.
Project-wide джерело правди по статусу; per-track деталі — у `docs/<track>/README.md`.

**Останнє оновлення:** 2026-06-03

---

## Current state (snapshot 2026-06-03)

| Metric | Value |
|--------|-------|
| Календарний час від старту | ~56 днів (2026-04-08 → 2026-06-03) |
| Commits | 199 |
| Tests passing | 190 |
| Tasks completed | M1 (5/5) + M2 (5/5) + M2.5 (eval/data) + Ingestion→production track + Verifier-v2 track (19.5→19.9) |
| Tasks in flight | Task 20 (VerificationOrchestrator) — spec landed, план next |
| Tasks queued | Recheck-луп, AWS deploy (23–24), CI (master-plan Task 20) |
| AWS cost | $0 (not deployed yet) |

**Активний фокус:** Verifier-v2 track. Split-verifier (19.9) у production-коді; зараз —
VerificationOrchestrator (Task 20, first-pass), що зв'язує `Verifier` з БД.

> **Нумерація:** verifier-v2 track має власну внутрішню нумерацію (19.5/19.7/19.8/19.9/20).
> Її "Task 20" (orchestrator) — це НЕ master-plan Task 20 (GitHub Actions CI). Master-план:
> [`docs/plan/2026-04-08-prophet-checker-plan.md`](docs/plan/2026-04-08-prophet-checker-plan.md).

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
| 19 — Integration smoke | `scripts/integration_smoke.py` (real Postgres + Telegram + LLM) |

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
| 20 — VerificationOrchestrator (first-pass) | 🚧 spec | [`docs/verification-track/20-verification-orchestrator/design.md`](docs/verification-track/20-verification-orchestrator/design.md) (`d8cd037`). План + імплементація — next |

**Допоміжне:** 3-стадійний pipeline `sample_arestovich_posts → run_extraction → run_verification`
для ручного рев'ю якості (`scripts/`, outputs у `scripts/outputs/pipeline_run/`).

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
