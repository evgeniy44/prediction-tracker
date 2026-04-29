# Verification Trigger Policy — Design

**Дата:** 2026-04-26
**Статус:** APPROVED — ready for implementation plan
**Supersedes:** Verification flow section in [`2026-04-07-prophet-checker-design.md`](../architecture/2026-04-07-prophet-checker-design.md) і open question у [`2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md) (Flow 5b "OPEN QUESTION 1")

---

## Problem statement

Original design 2026-04-07 декларує: «verification can be delayed — a prediction about 'summer 2023' can only be verified after summer 2023». Without механізму як саме визначати «після».

Поточна реалізація (`PostgresPredictionRepository.get_unverified()`) повертає **всі** UNRESOLVED predictions без time-gate — тобто LLM попросять верифікувати претенди типу «Війна закінчиться у 2027», подія яких ще не відбулась.

Empirical data з Task 13.5 показує що **70-90% LLM-витягнутих predictions мають `target_date=null`** (Flash Lite 23%, DeepSeek 11%, Pro Preview 17%, Sonnet 44%). Strict target_date gating виключив би ≥77% корпусу — нежиттєздатно.

Без явної policy:
- `PredictionVerifier` не може потрапити у production (Task 15 orchestrator не може використати його)
- Predictions без target_date нікуди не йдуть з queue
- Premature predictions (подія в майбутньому) дають шумний `unresolved` verdict

---

## Architectural decision

**Pattern: Smart Verifier with Dumb Trigger.**

Verifier сам ухвалює рішення «чи можна верифікувати зараз» як частина свого LLM-call (без додаткових calls). Trigger logic у scheduler/orchestrator — тривіальний SQL-фільтр.

**Чому не Smart Trigger + Dumb Verifier:**
- Trigger без full claim context не може визначити чи подія сталась → треба окремий LLM-call (`is_verifiable_now?`) перед кожним verify → ×2 calls.
- Verifier і так має повний context (claim text, dates, post excerpt). Розширити його prompt коштує 0 додаткових calls.

**Чому не Hybrid (target_date defined → smart trigger; null → smart verifier):**
- Додає branching у логіці. Можлива оптимізація на майбутнє, але YAGNI зараз.

**Empirical validation:** на 10 random Flash Lite claims прогнали v1 prompt з 4-status. Результат: 8/10 clean verdicts, 2 знайдених проблеми (Opus inconsistency на mutual-exclusion, hedging замість confirmed). Обидві проблеми вирішуються prompt tightening — не міняють architecture. Деталі: `scripts/outputs/extraction_eval/verifier_4status_test.json`.

---

## Architecture overview

```
                ┌─────────────────────┐
                │  Trigger Scheduler  │  (cron-like, e.g. daily/hourly)
                └──────────┬──────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────┐
    │  PredictionRepository.get_eligible_for_      │
    │  verification(today, limit)                  │
    │                                              │
    │  SQL: WHERE verified_at IS NULL              │
    │    AND (next_check_at IS NULL                │
    │         OR next_check_at <= today)           │
    │    AND (max_horizon IS NULL                  │
    │         OR max_horizon >= today)             │
    └──────────────────────┬───────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────┐
    │  PredictionVerifier.verify(prediction, today)│
    │                                              │
    │  Single LLM call returning:                  │
    │   • status: confirmed/refuted/unresolved/    │
    │             premature                        │
    │   • prediction_strength (set once)           │
    │   • max_horizon (set once if needed)         │
    │   • retry_after (only if premature)          │
    │   • verdict-confidence + reasoning           │
    └──────────────────────┬───────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     status terminal   status=premature   max_horizon
     (C/R/U)           + retry_after      passed?
                       within max_horizon  
            ▼              ▼              ▼
     verified_at=NOW  next_check_at      force status=
     status=verdict   = retry_after      unresolved
                      stays in queue     (separate pass)
```

**Ключові властивості:**
- Trigger logic тривіальний — SQL без LLM.
- Verifier — single source of truth для всіх рішень про prediction lifecycle.
- No infinite loops — `max_horizon` гарантує finite check window.
- Idempotent: повторний verify на тому ж claim дає той самий verdict (з винятком terminal status, який не перевіряється повторно).

---

## Verifier output schema

```json
{
  "status": "confirmed" | "refuted" | "unresolved" | "premature",
  "confidence": 0.0,
  "prediction_strength": "low" | "medium" | "high",
  "reasoning": "1-3 sentences",
  "evidence": "concrete fact / URL or null",
  "retry_after": "YYYY-MM-DD or null",
  "max_horizon": "YYYY-MM-DD or null"
}
```

### Field definitions

**Verdict block:**
- `status` — 4 варіанти. `unresolved` тепер — terminal (recheck не допоможе); `premature` — in-flight (will retry).
- `confidence` 0.0–1.0 — впевненість у верді́кті.
- `reasoning` — 1-3 речення.
- `evidence` — concrete fact / URL. null коли verdict=unresolved/premature.

**Strength block (set once on first verification):**
- `prediction_strength` — оцінює сам claim, не verdict:
  - `high` — concrete falsifiable з measurable outcome
  - `medium` — probabilistic але substantive
  - `low` — vague hedge / possibility statement / non-substantive

**Time-gating block:**
- `retry_after` — тільки коли `status=premature`. Інакше null.
- `max_horizon` — set ONLY якщо `status=premature` AND `target_date IS NULL`. Якщо target_date defined — нативно служить limit, max_horizon=null.

### Mutual-exclusion constraints

| Combination | Validity |
|-------------|----------|
| status=confirmed/refuted | `evidence` НЕ null, `retry_after` null |
| status=unresolved | `retry_after` null (recheck не допоможе) |
| status=premature | `retry_after` НЕ null, `evidence` може бути null |
| status≠premature AND retry_after≠null | ❌ invalid — drop retry_after, log warning |

Enforced by `parse_verification_response_v2()` — invalid combinations log warning і normalized.

---

## Storage changes

### Domain `Prediction` (`src/prophet_checker/models/domain.py`)

```python
class PredictionStrength(str, Enum):  # NEW
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Prediction(BaseModel):
    # ... existing fields ...
    
    # NEW
    prediction_strength: PredictionStrength | None = None
    max_horizon: date | None = None
    next_check_at: date | None = None
    verify_attempts: int = 0
```

**Дизайн-рішення:** `PREMATURE` НЕ persisted у `status`. Це in-flight state, описується через combination:
- `status=UNRESOLVED, verified_at=NULL, next_check_at=DATE` → "premature, retry at next_check_at"
- `status=UNRESOLVED, verified_at=NOW, next_check_at=NULL` → "terminal, didn't resolve"

Один enum-value (`PREMATURE`) лише describing transient state — не варто persistence.

### ORM `PredictionDB` (`src/prophet_checker/models/db.py`)

```python
prediction_strength: Mapped[str | None] = mapped_column(String(10), nullable=True)
max_horizon: Mapped[date | None] = mapped_column(Date, nullable=True)
next_check_at: Mapped[date | None] = mapped_column(Date, nullable=True)
verify_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

Plus індекс для trigger query:
```sql
CREATE INDEX idx_predictions_eligible
ON predictions (verified_at, next_check_at, max_horizon);
```

### Repository interface (`storage/interfaces.py`)

Замінюємо існуючий `get_unverified()` на:

```python
class PredictionRepository(Protocol):
    async def get_eligible_for_verification(
        self, today: date, limit: int = 100
    ) -> list[Prediction]: ...
    
    async def force_unresolved_past_horizon(self, today: date) -> int: ...
    # Bulk-update: predictions with max_horizon<today AND verified_at=NULL
    # → status=unresolved, verified_at=today, evidence_text='exceeded max_horizon'
    # Returns: count of updated rows
```

### Alembic migration

Нова revision `add_verification_metadata`:
- ADD COLUMN prediction_strength VARCHAR(10) NULL
- ADD COLUMN max_horizon DATE NULL
- ADD COLUMN next_check_at DATE NULL
- ADD COLUMN verify_attempts INTEGER DEFAULT 0 NOT NULL
- CREATE INDEX idx_predictions_eligible

Existing rows: всі нові поля NULL/0 — нормально, наступний verifier-pass виставить.

---

## State machine

```
              ┌──────────────────────┐
              │  EXTRACTED (initial) │
              │                      │
              │  status=UNRESOLVED   │
              │  verified_at=NULL    │
              │  next_check_at=NULL  │
              │  prediction_strength │
              │     =NULL            │
              │  max_horizon=NULL    │
              │  verify_attempts=0   │
              └──────────┬───────────┘
                         │
                         │ initial verify (verify_attempts: 0 → 1)
                         │ verifier sets prediction_strength + max_horizon
                         ▼
       ┌─────────────────┴──────────────────────────┐
       │                                            │
       ▼                                            ▼
  ┌──────────────┐                  ┌─────────────────────────────────┐
  │  TERMINAL    │                  │  IN-FLIGHT (premature)          │
  │              │                  │                                  │
  │  status=     │                  │  status=UNRESOLVED              │
  │  confirmed/  │                  │  verified_at=NULL               │
  │  refuted/    │                  │  next_check_at=YYYY-MM-DD       │
  │  unresolved  │                  │  prediction_strength=set        │
  │  verified_at │                  │  max_horizon=set or null        │
  │  =NOW        │                  │  verify_attempts=N              │
  │  evidence    │                  └─────────────┬───────────────────┘
  │  populated   │                                │
  └──────────────┘                                │
       ▲                                          │
       │                                          │
       │ ┌────────────────────────────────────────┴───────────┐
       │ │                                                    │
       │ ▼                                                    ▼
       │ next_check_at <= TODAY                  max_horizon < TODAY
       │ AND max_horizon >= TODAY                AND still verified_at=NULL
       │                                                       │
       │ verify again (attempts++)                              │
       │ → loop back through verifier                           │
       │                                                       ▼
       │                                          force_unresolved_past_horizon()
       │                                          status=unresolved
       │                                          verified_at=NOW
       └──────────────────────────────────────────evidence='exceeded max_horizon'
```

---

## Orchestration cycle

```python
async def verification_cycle(today: date):
    # Step 1: housekeeping — finalize all expired-horizon predictions
    n_finalized = await pred_repo.force_unresolved_past_horizon(today)
    if n_finalized:
        logger.info("Finalized %d predictions past max_horizon", n_finalized)
    
    # Step 2: pull batch of eligible predictions
    eligible = await pred_repo.get_eligible_for_verification(today, limit=BATCH)
    if not eligible:
        return
    
    # Step 3: verify each
    for pred in eligible:
        result = await verifier.verify(pred, today=today)
        await apply_result(pred, result, today)


async def apply_result(pred: Prediction, result: VerificationResult, today: date):
    pred.verify_attempts += 1
    
    # Set-once fields (only if not already populated)
    if pred.prediction_strength is None:
        pred.prediction_strength = result.prediction_strength
    if pred.max_horizon is None and result.max_horizon:
        pred.max_horizon = result.max_horizon
    
    if result.status == "premature":
        pred.next_check_at = result.retry_after
        # verified_at stays NULL → still in queue
    else:
        # Terminal: confirmed / refuted / unresolved
        pred.status = result.status
        pred.confidence = result.confidence
        pred.evidence_url = result.evidence_url
        pred.evidence_text = result.evidence
        pred.verified_at = today
        pred.next_check_at = None
    
    await pred_repo.update(pred)
```

---

## Verification prompt v2

Замінює `VERIFICATION_SYSTEM` + `VERIFICATION_TEMPLATE` в `src/prophet_checker/llm/prompts.py:90-108`.

### `VERIFICATION_SYSTEM_V2`

```
You are a fact-checker who verifies political/economic predictions about Ukraine
and global events. Today's date is {today}. The prediction was made on a past
date — your job is to assess whether it can be evaluated NOW, and if so, what
the verdict is.

Determine FOUR outputs:

═══════════════════════════════════════════════════════════════════
1) STATUS — exactly one of:

   "confirmed" — the predicted event happened as foretold. You have
                concrete evidence. The prediction's timeframe (target_date,
                or reasonable interpretation) has passed.

   "refuted"  — the predicted event did NOT happen, OR the opposite occurred.
                Concrete evidence required. Timeframe has passed.

   "unresolved" — the predicted event's timeframe has passed, but evidence is
                  ambiguous, the claim is too vague to falsify, or no public
                  record exists. Re-checking later WON'T help — this is a
                  permanent verdict.

   "premature" — the predicted event has not yet occurred but is still
                 POSSIBLE. The timeframe hasn't elapsed, OR the trigger
                 condition (for conditional predictions like "if X happens")
                 hasn't fired. We should retry verification later.

═══════════════════════════════════════════════════════════════════
2) PREDICTION_STRENGTH — assess the CLAIM ITSELF (independent of outcome):

   "high"   — concrete falsifiable claim with measurable outcome.
              Example: "Trump will end the war by April 30, 2025"

   "medium" — probabilistic but substantive claim with clear outcome.
              Example: "There's a high probability Russia will mobilize
              500k more troops by 2026"

   "low"    — vague hedge, possibility statement, or non-substantive
              forecast. Example: "Armed clashes are possible in the Baltics"
              ("possible" is not a forecast — it's a risk description)

═══════════════════════════════════════════════════════════════════
3) MAX_HORIZON — latest reasonable date to keep checking this prediction.
   Set ONLY if status="premature" AND target_date is null. Otherwise null.

   Heuristics:
   • Conditional ("if X happens, then Y"): max_horizon = today + lifespan
     of condition X. E.g. political-power conditionals ~3 years (election cycle).
   • Open-ended political ("Zelensky will lose power"): today + 5 years.
   • "Soon" / "in the coming weeks/months": prediction_date + 1-2 years.
   • Far-future explicit ("in 10 years"): use the implied date.

   If max_horizon < today already → don't set premature; pick terminal verdict.

═══════════════════════════════════════════════════════════════════
4) RETRY_AFTER — only when status="premature". When does it make sense to
   re-evaluate?

   • For conditional: today + 3-6 months (recheck if trigger fired).
   • For target_date in future: target_date itself.
   • For vague open-ended: today + 6 months.

═══════════════════════════════════════════════════════════════════
MUTUAL EXCLUSION RULES (strictly enforce):
- status=confirmed/refuted → evidence MUST be a concrete fact, retry_after=null
- status=unresolved → retry_after=null (recheck won't help)
- status=premature → retry_after MUST be a date, evidence may be null
- max_horizon set ONLY when status=premature AND target_date=null

Respond ONLY with raw JSON, no markdown fences:

{{
  "status": "confirmed" | "refuted" | "unresolved" | "premature",
  "confidence": 0.0 to 1.0,
  "prediction_strength": "low" | "medium" | "high",
  "reasoning": "1-3 sentences explaining the verdict and strength",
  "evidence": "concrete fact or URL, or null",
  "retry_after": "YYYY-MM-DD or null",
  "max_horizon": "YYYY-MM-DD or null"
}}
```

### `VERIFICATION_TEMPLATE_V2`

```
Claim: "{claim}"
Made on: {prediction_date}
Expected by: {target_date}

Original post excerpt (for context):
---
{post_excerpt}
---

Today: {today}.

Provide your verdict per the rubric.
```

### Backward compatibility

`VERIFICATION_SYSTEM` (старий) залишається з `# DEPRECATED` markером. Новий `VERIFICATION_SYSTEM_V2` paralelno. Eventually old → видалити після миграції tests.

`parse_verification_response` (3-field parser) залишається. Новий `parse_verification_response_v2` (7-field, з mutual-exclusion validation) — додається.

---

## Edge cases

| Сценарій | Поведінка |
|----------|-----------|
| Прогноз з `target_date` у минулому, target_date < TODAY | Verifier дає terminal (C/R/U); не premature |
| Прогноз з `target_date` у майбутньому | Verifier дає `premature, retry_after=target_date`. max_horizon=null (target_date вже limit) |
| Прогноз без `target_date`, vague | На першому verify: prediction_strength=low, max_horizon=prediction_date+2y. Якщо premature — петля до max_horizon |
| Прогноз conditional ("якщо X") | premature, retry_after=NOW+6m, max_horizon=NOW+5y або lifecycle of condition |
| Verifier помилився, повернув confirmed → пізніше виявилось refuted | Поточний design: terminal — більше не verify. Future: manual re-trigger via UI, set verified_at=NULL |
| LLM call fails / timeout | verify_attempts++, status поля не змінюються; повертаємо у чергу з next_check_at=NOW+1h |
| `max_horizon < TODAY` ще на першому verify (давня прогноза, ніколи не верифікована) | Verifier дає terminal (C/R/U) як завжди. max_horizon тут вже passed — поле не використовується |
| Багато premature ітерацій підряд (verify_attempts=10+) | Telemetry: log warning. Корисно для monitoring якості prompt'у |

---

## Telemetry

`verify_attempts` поле дає основу для quality monitoring:
- avg attempts per terminal verdict (надмірно високе = prompt погано judges retry_after)
- distribution attempts vs prediction_strength (low може мати більше attempts)
- predictions stuck near max_horizon (близько до finalize-by-timeout)

`prediction_strength` distribution per author:
- 80% high-strength forecasts vs 20% low-strength → public figure-level metric
- Drift over time (last 6 months strength vs all-time)

---

## Testing strategy

| Group | Tests | Notes |
|-------|------:|-------|
| A — Pure functions (prompt build, response parse) | 12 | Швидкі, нема I/O |
| B — Domain + Storage | 9 | testcontainers або pytest-postgresql fixtures |
| C — Verifier class | 9 | Mock LLMClient |
| D — Orchestration cycle | 6 | Mock verifier + repo |
| E — E2E integration | 3 | Mock LLM, real DB |
| Manual empirical | 1 run | 10 claims via Opus, validate v2 prompt |
| **TOTAL** | **~39 tests** | |

Деталізація — у implementation plan (наступний крок після цього design).

### Manual empirical re-run

Перед staging implementation: повторити 10-claim experiment з v2 prompt'ом (зберігати у `scripts/outputs/extraction_eval/verifier_v2_test.json`). Перевірити що Opus:
- розрізняє low/medium/high на тих самих 10 claims
- правильно ставить max_horizon для open-ended
- не дає inconsistency (unresolved+retry_after як на #5 v1 prompt'у)

---

## Migration path

1. **Schema migration** (Alembic revision) — додає 4 поля + index. Безпечно для existing rows (NULL defaults).
2. **Add new prompt + parser** в `prompts.py` paralelno зі старими.
3. **Add new methods** до `PredictionRepository` (`get_eligible_for_verification`, `force_unresolved_past_horizon`).
4. **PredictionVerifier v2** — нова логіка `verify(pred, today)` з 7-field result. Старий `verify(pred)` deprecated.
5. **Add orchestration** (`verification_cycle`) — у Task 15 ingestion module.
6. **Integration tests** + manual empirical run.
7. **Switch over**: ingestion orchestrator використовує v2; old API залишається deprecated до next cleanup.
8. **Cleanup**: видалити old prompt, parser, get_unverified() — після того як tests усі мігровані.

---

## Open questions deferred

Ці питання НЕ блокують implementation цього design'у:

- **Re-verification policy** для випадків коли verdict помилився (UI re-trigger).
- **Prediction strength feedback loop** до extraction prompt — якщо много low-strength витягається, треба покращити criterion 4 substantiveness в EXTRACTION_SYSTEM.
- **News collector for evidence** — поки що Opus покладається на свої training knowledge для evidence. Future: LiteLLM web_search_options або dedicated NewsCollector (Task 22).
- **Manual queue** для predictions з `prediction_strength=low` AND high `verify_attempts` — UI для manual review.

---

## Cross-references

- Architecture refresh: [`2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md)
- Original design: [`2026-04-07-prophet-checker-design.md`](../architecture/2026-04-07-prophet-checker-design.md)
- Empirical 10-claim test (v1 prompt): `scripts/outputs/extraction_eval/verifier_4status_test.json`
- Master plan: [`2026-04-08-prophet-checker-plan.md`](../plan/2026-04-08-prophet-checker-plan.md)
