# `docs/` — index

Документи згруповані за use-case. Кожна підпапка — один логічний контур (фіча / задача / процес).

## 📋 [`plan/`](plan/) — project tracking

Master plan + status. Living documents.

| Документ | Призначення |
|----------|-------------|
| [`2026-04-08-prophet-checker-plan.md`](plan/2026-04-08-prophet-checker-plan.md) | Master plan: всі задачі (M1–M6), milestones, retrospective notes per task |
| [`progress.md`](plan/progress.md) | Progress log (наразі stale, фіксує тільки Phase 0 — потребує оновлення) |

## 🏛 [`architecture/`](architecture/) — architectural specs

Що ми будуємо і чому.

| Документ | Призначення |
|----------|-------------|
| [`2026-04-07-prophet-checker-design.md`](architecture/2026-04-07-prophet-checker-design.md) | Original design — модулі, схема БД, AWS topology. Historical reference. |
| [`2026-04-26-architecture-current.md`](architecture/2026-04-26-architecture-current.md) | **Current state with focus on data flows.** 5 active pipelines + module inventory + open questions. Living document. |

## 🔬 [`extraction-quality-eval/`](extraction-quality-eval/) — Task 13.5

Вимірювання якості claim extraction (LLM-as-judge). Closeout: Pro Preview виграв за precision (avg 2.30), Flash Lite залишився production вибором (recall 73%, 33× дешевше).

| Документ | Призначення |
|----------|-------------|
| [`2026-04-21-extraction-quality-eval-design.md`](extraction-quality-eval/2026-04-21-extraction-quality-eval-design.md) | Spec: 3-stage LLM-as-judge eval, 6-value verdict, gold-blind judge prompt |
| [`2026-04-21-extraction-quality-eval-plan.md`](extraction-quality-eval/2026-04-21-extraction-quality-eval-plan.md) | Implementation plan — 10 tasks, ~28 TDD tests |
| [`2026-04-26-extraction-consolidated-report.md`](extraction-quality-eval/2026-04-26-extraction-consolidated-report.md) | Per-post per-model report з вердиктами Opus (15 YES + 8 NO постів) |
| [`2026-04-26-gemini-pro-vs-lite-cost.md`](extraction-quality-eval/2026-04-26-gemini-pro-vs-lite-cost.md) | Cost comparison: Pro Preview $115 vs Flash Lite $3.50 на 5572 постах. Two-tier strategy hypothesis. |

## 🔮 [`verifier-v2/`](verifier-v2/) — verification trigger policy

Smart Verifier з Dumb Trigger: 4-status output (confirmed/refuted/unresolved/premature), prediction_strength, max_horizon, retry-loop semantics. Розв'язує проблему target_date=null у 70-90% claims.

| Документ | Призначення |
|----------|-------------|
| [`2026-04-26-verification-trigger-policy-design.md`](verifier-v2/2026-04-26-verification-trigger-policy-design.md) | Spec: full design + state machine + edge cases |
| [`2026-04-29-verification-trigger-policy-plan.md`](verifier-v2/2026-04-29-verification-trigger-policy-plan.md) | Implementation plan — 9 TDD tasks, 58 steps, ~30 tests + empirical re-run |
| [`2026-04-29-verifier-v2-data-flows.md`](verifier-v2/2026-04-29-verifier-v2-data-flows.md) | 5 ASCII diagrams: single call / lifecycle / trigger logic / full cycle / v1 vs v2 |

## 📝 [`annotation/`](annotation/) — Task 12 manual gold labeling

| Документ | Призначення |
|----------|-------------|
| [`annotation-guidelines.md`](annotation/annotation-guidelines.md) | Rubric: YES/NO criteria, anti-patterns. Використовується для gold_labels.json і extraction-eval judge prompt. |

---

## Чому ця структура

Документи про одну фічу/задачу часто пишуться парою (`design.md` + `plan.md`) і доповнюються артефактами (cost-comparison, data-flows, reports). Тримати їх у одній subdir дозволяє:
- одразу бачити повний контекст use-case
- спрощує навігацію (12 файлів flat — складно сканувати)
- очевидне місце для нових артефактів — додаючи новий cost analysis для extraction, кладемо в `extraction-quality-eval/` без роздумів

## Conventions

- Імена файлів: `YYYY-MM-DD-<topic>.md` — дата творення (не оновлення).
- Cross-references використовують relative paths.
- Master plan і architecture-current — **living documents**, оновлюються з кожним milestone.
- `progress.md` — застарілий і потребує оновлення (TODO).
