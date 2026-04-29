# Prediction Tracker — Progress Log

Living log: time, cost, deliverables. Оновлюється коли завершується milestone або значуща задача.

**Останнє оновлення:** 2026-04-29

---

## Current state (snapshot 2026-04-29)

| Metric | Value |
|--------|-------|
| Календарний час від старту | ~21 день (2026-04-08 → 2026-04-29) |
| Commits | 53 |
| Tests passing | 88 (60 detection + 28 extraction quality + analysis/llm/storage unit tests) |
| Tasks completed | M1 (5/5) + M2 (5/5) + M2.5 (4/5 done, 1 deferred, 1 removed) |
| Tasks in flight | Task 21 (Telegram source adapter — brainstorm started) |
| Tasks queued | 15, 16, 17, 18, 19, 23, 24 (ingestion → AWS deploy track) |
| AWS cost | $0 (not deployed yet) |

**Активний фокус:** ingestion-to-AWS deploy. Verifier v2 design готовий, але implementation deferred поки production pipeline не запрацює.

---

## Phase 0: Brainstorming + Planning + Task 0 ✅ COMPLETE

**Date:** 2026-04-08
**Duration:** ~2 hours (one session)

| Step | Deliverable |
|------|------------|
| Brainstorm | Ідея, tech stack, архітектурні рішення |
| Design spec | DELETED 2026-04-29 → superseded by [`../architecture/2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md) |
| Implementation plan | [`2026-04-08-prophet-checker-plan.md`](2026-04-08-prophet-checker-plan.md) — living doc, оновлюється з кожним milestone |
| Todoist project | 19 задач + ~90 підзадач + 6 content задач |
| Task 0 | GitHub repo + README + LICENSE + .gitignore (commit `83fc1dc`) |

**Key decisions:** Python/FastAPI, monolith-first, Protocol-based storage abstraction, LiteLLM, PostgreSQL + pgvector, AWS RDS + EC2 deploy.

---

## Phase 1: M1 Foundation (Tasks 0-4) ✅ COMPLETE

| Task | Commit | Tests |
|------|--------|------:|
| 0 — GitHub repo + scaffold | `83fc1dc`, `693995a` | — |
| 1 — Project scaffold + config | `2f736de` | 2 |
| 2 — Domain models (Pydantic) | `04e195c` | 6 |
| 3 — Storage interfaces (Protocol) | `035468e` | 7 |
| 4 — SQLAlchemy ORM + Alembic config | `1ca8a16` | 1 |

**Total:** 5 tasks, 16 tests.

---

## Phase 2: M2 AI Pipeline (Tasks 5-9) ✅ COMPLETE

| Task | Commit | Tests |
|------|--------|------:|
| 5 — PostgreSQL storage impl | `cd25af0` | 5 |
| 6 — LLM client (LiteLLM) | `f90eb07` | 3 |
| 7 — Prompt templates | `006a458` | 8 |
| 8 — PredictionExtractor | `610b0dd` | 3 |
| 9 — PredictionVerifier (v1) | `20746b8` | 4 |

**Total:** 5 tasks, ~23 tests. PredictionVerifier v1 буде superseded Verifier v2 (design ready).

---

## Phase 3: M2.5 Eval & Data 🟡 MOSTLY COMPLETE

| Task | Status | Notes |
|------|--------|-------|
| 10 — Збір реальних постів з Telegram | ✅ | 5572 Arestovich posts via Telethon (`d7c9e5e`) |
| 11 — YouTube transcripts | ❌ removed | MVP trimmed to Telegram-only (2026-04-20) |
| 12 — Gold labels (manual annotation) | ✅ | 130 розмічених постів (97 Arestovich + 33 інші); commits `428aea4` → `a992e0f` |
| 13 — Detection evaluation | ✅ | 5 моделей × 2 prompt versions; **Winner:** Gemini 3.1 Flash Lite, F1=0.848 (`3da94a3`) |
| 13.5 — Extraction quality evaluation | ✅ | 3-stage LLM-as-judge eval; 4 моделі × Opus judge; **Winner за avg_score:** Pro Preview (2.30); **production decision:** Flash Lite (33× дешевше, кращий recall) |
| 14 — Smoke test on full corpus | ⏸ deferred | Task 13.5 дав достатньо empirical signal на 97 постах |

**Знахідки Phase 3:**
- Sonnet 4.6 катастрофічно слабкий на extraction (1/15 YES recall) — surprising.
- 70-90% extracted claims мають `target_date=null` → блокує v1 verifier (треба Verifier v2).
- Two-tier strategy (Flash Lite + Pro Preview) — open hypothesis, потребує proof-of-concept.

---

## Phase 3.5: Design Refresh ✅ COMPLETE

Період 2026-04-26 → 2026-04-29: накопичена бібліотека design docs після Phase 3. Не була в original plan, але emergent потреба.

**Deliverables:**
- [`architecture/2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md) — index + 7 окремих flow docs з Mermaid діаграмами
- [`verifier-v2/2026-04-26-verification-trigger-policy-design.md`](../verifier-v2/2026-04-26-verification-trigger-policy-design.md) — spec для Verifier v2 (4-status, retry-loop, set-once metadata)
- [`verifier-v2/2026-04-29-verification-trigger-policy-plan.md`](../verifier-v2/2026-04-29-verification-trigger-policy-plan.md) — TDD implementation plan (9 tasks, ~30 tests)
- 3 data flow docs для verifier-v2 (verifier-call, prediction-lifecycle, verification-cycle)
- [`extraction-quality-eval/2026-04-26-gemini-pro-vs-lite-cost.md`](../extraction-quality-eval/2026-04-26-gemini-pro-vs-lite-cost.md) — cost comparison
- [`extraction-quality-eval/2026-04-26-extraction-consolidated-report.md`](../extraction-quality-eval/2026-04-26-extraction-consolidated-report.md) — per-post per-model report
- Reorganization: `docs/` згруповано у 5 subdirs за use-case; `scripts/` reorg на `data/` + `outputs/`

---

## Phase 4: M3 Orchestration (Tasks 21, 15, 16) 🚧 STARTING

**Активна траєкторія: ingestion-to-AWS deploy.**

| Task | Status | Doc |
|------|--------|-----|
| 21 — Source adapter (Telegram) | 🚧 brainstorm started | [`flow-production-ingestion.md`](../architecture/2026-04-26-flow-production-ingestion.md) |
| 15 — Ingestion orchestrator | 📋 queued | [`flow-production-ingestion.md`](../architecture/2026-04-26-flow-production-ingestion.md) |
| 16 — FastAPI app entry | 📋 queued | — |

**Out of MVP scope (deferred):** Verifier v2 implementation, Detection prefilter (`PredictionDetector`), Task 22 (News collector), Bot module, RAG endpoint.

---

## Phase 5: M4 Database & Integration (Tasks 17-19) 📋 QUEUED

| Task | Status |
|------|--------|
| 17 — Docker + Docker Compose | 📋 |
| 18 — Alembic migration on real Postgres | 📋 |
| 19 — Integration smoke test | 📋 |

---

## Phase 6: M5 AWS Deploy (Tasks 23-24) 📋 QUEUED

| Task | Status |
|------|--------|
| 23 — AWS RDS PostgreSQL + pgvector | 📋 |
| 24 — AWS EC2 + Docker deploy | 📋 |
| 20 — GitHub Actions CI | 📋 (опціонально, після deploy) |

---

## Phase 7: Future (post-MVP)

Послідовність після того як ingestion live на AWS:

1. Verifier v2 implementation (plan ready)
2. Detection prefilter (`PredictionDetector`) — якщо вирішимо two-tier
3. Bot module (Telegram chat frontend)
4. RAG query endpoint
5. Task 22 (News collector) — для verifier evidence
6. Continuous eval-loop (production quality monitoring)

---

## Cost log (approximate)

| Категорія | Cost |
|-----------|------|
| LLM API (eval runs — detection + extraction quality) | ~$15-20 |
| Claude Code dev (numerous Opus sessions) | ~$50-200 (estimated, hard to track) |
| AWS | $0 |
| GitHub | $0 (public) |
| **Total to date** | **~$70-220** |

---

## Notes

- **Velocity** ~ 2.5 commits/день calendar (53 commits / 21 day). Реальний робочий день — менше; pet project pace.
- **Tests pace:** 88 tests / 21 days = ~4 tests/день calendar.
- **Post-Phase-3 pivot:** замість прямого переходу до M3 (як в original plan), ми пройшли Phase 3.5 design refresh — знайшли + усунули проблему 70-90% null target_date через Verifier v2 design. Ця затримка реальна, але економить implementation work later.
