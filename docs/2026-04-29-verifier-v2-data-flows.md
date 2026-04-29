# Verifier v2 — Data Flow Diagrams

**Дата:** 2026-04-29
**Доповнює:** [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md) (the spec)
**Статус:** Reference visualization — for understanding, not implementation gate

Цей документ — це **5 візуалізацій** Verifier v2 на різних рівнях деталізації.
Спершу читай spec для контексту; візуалізації нижче — для швидкого огляду «як воно тече».

---

## 1. Single verification call — `verify_v2(prediction, today, post_excerpt)`

Що відбувається у момент виклику verifier'а на ОДНУ prediction.

```
                  Caller (orchestrator або scheduler)
                              │
                              │ verify_v2(prediction, today, post_excerpt)
                              ▼
            ┌───────────────────────────────────────┐
            │ PredictionVerifier.verify_v2()        │
            │  src/prophet_checker/analysis/        │
            │     verifier.py                       │
            └────────────┬──────────────────────────┘
                         │
                         │ verify_attempts += 1  (always, even on failure)
                         │
                         ▼
            ┌───────────────────────────────────────┐
            │ build_verification_prompt_v2()        │
            │  inputs: claim_text, prediction_date, │
            │          target_date, post_excerpt,   │
            │          today                        │
            └────────────┬──────────────────────────┘
                         │
                         │ user-message text
                         ▼
            ┌───────────────────────────────────────┐
            │ get_verification_system_v2(today)     │
            │  returns SYSTEM prompt with {today}   │
            │  injected, 4-status rubric,           │
            │  strength rubric, mutual-exclusion    │
            └────────────┬──────────────────────────┘
                         │
                         │ system-message text
                         ▼
            ┌───────────────────────────────────────┐
            │ self._llm.complete(prompt, system)    │
            │  LiteLLM → Anthropic Opus 4.6         │
            │  (or any other provider)              │
            └────────────┬──────────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
        SUCCESS                   FAILURE
        raw text                  Exception
            │                         │
            ▼                         │
   ┌────────────────────┐             │
   │ parse_verification │             │
   │ _response_v2(raw)  │             │
   │  - strip fence     │             │
   │  - find first {    │             │
   │  - raw_decode      │             │
   │  - validate enums  │             │
   │  - apply mutual-   │             │
   │    exclusion rules │             │
   └─────────┬──────────┘             │
             │                        │
   ┌─────────┴─────────┐              │
   │                   │              │
   ▼                   ▼              │
 OK result        invalid /           │
                  parse error         │
   │                   │              │
   │                   └──────────────┤
   │                                  │
   ▼                                  ▼
                                 Return prediction
                                 unchanged (only
                                 verify_attempts++)
                                 verified_at stays NULL
                                 — no LLM cost wasted
                                 on retry, but next
                                 cycle will try again
   │
   │ result = VerificationResult(status, confidence,
   │   prediction_strength, reasoning, evidence,
   │   retry_after, max_horizon, verdict_invalid)
   ▼
┌──────────────────────────────────────────────┐
│ Apply set-once metadata                      │
│                                              │
│  if prediction.prediction_strength is None:  │
│      prediction.prediction_strength =        │
│          PredictionStrength(result.strength) │
│                                              │
│  if prediction.max_horizon is None and       │
│     result.max_horizon is not None:          │
│      prediction.max_horizon =                │
│          result.max_horizon                  │
└─────────────────┬────────────────────────────┘
                  │
       ┌──────────┴───────────┐
       │                      │
       ▼                      ▼
  result.status         result.status
  == "premature"        in (confirmed/refuted/unresolved)
       │                      │
       ▼                      ▼
┌─────────────────┐   ┌─────────────────────────────┐
│ IN-FLIGHT       │   │ TERMINAL                    │
│                 │   │                             │
│ next_check_at = │   │ status = result.status      │
│ result.         │   │ confidence = result.        │
│   retry_after   │   │   confidence                │
│                 │   │ evidence_text = result.     │
│ verified_at     │   │   evidence                  │
│   stays NULL    │   │ verified_at = today         │
│                 │   │ next_check_at = NULL        │
│ status = stays  │   │                             │
│   UNRESOLVED    │   │                             │
└────────┬────────┘   └──────────┬──────────────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
          return prediction (mutated)
```

**Інваріанти, які тримаються:**

- `verify_attempts` ВЖЕ ЗБІЛЬШЕНО, навіть якщо все інше провалилось.
- `prediction_strength` і `max_horizon` встановлюються **раз** (set-once); подальші виклики їх не переписують.
- `next_check_at` і `verified_at` — взаємно виключаючі: in-flight prediction має `next_check_at != NULL AND verified_at = NULL`; terminal — навпаки.

---

## 2. Lifecycle of a Prediction — multiple verifications over time

Що відбувається з ОДНОЮ prediction між моментом її створення (extraction) і terminal verdict.

```
T₀ — extraction (Task 15 future orchestrator buduje prediction)
═════════════════════════════════════════════════════════════
{
  status:             UNRESOLVED  (default initial)
  verified_at:        NULL
  next_check_at:      NULL
  prediction_strength: NULL  (will be set on first verify)
  max_horizon:        NULL  (will be set if applicable)
  verify_attempts:    0
}

      │
      │ scheduler-cycle picks it up:
      │   get_eligible_for_verification(today=T₁) → [pred]
      │   (eligible because verified_at IS NULL,
      │    next_check_at IS NULL, max_horizon IS NULL)
      │
      ▼

T₁ — first verification call
═════════════════════════════════════════════════════════════
verifier.verify_v2(pred, today=T₁)
   LLM returns:
     status = "premature"
     prediction_strength = "medium"
     retry_after = T₁ + 6 months
     max_horizon = T₁ + 5 years
     reasoning = "vague forward statement, give it time"

After call:
{
  status:             UNRESOLVED  (unchanged — premature)
  verified_at:        NULL  (still in queue)
  next_check_at:      T₁ + 6m  (set!)
  prediction_strength: "medium"  (set once!)
  max_horizon:        T₁ + 5y  (set once!)
  verify_attempts:    1
}

      │
      │ time passes — between T₁+1d and T₁+6m,
      │   prediction is INVISIBLE to scheduler
      │   (next_check_at > today excludes it)
      │
      ▼

T₂ = T₁ + 6m — second verification call
═════════════════════════════════════════════════════════════
   get_eligible(today=T₂) → [pred]
     (next_check_at == T₂ ≤ today, max_horizon > today)

verifier.verify_v2(pred, today=T₂)
   LLM still finds no concrete evidence:
     status = "premature"
     retry_after = T₂ + 1 year
     prediction_strength = "medium"  (verifier returns it but is IGNORED — set-once)
     max_horizon = ...                (also IGNORED — set-once)

After call:
{
  next_check_at:      T₂ + 1y
  verify_attempts:    2
  // strength + max_horizon UNCHANGED (set-once)
}

      │
      │ continue looping...
      │
      ▼

T_n — eventually one of two things happens
═════════════════════════════════════════════════════════════
  (a) LLM finds evidence → terminal
        verifier returns status=confirmed/refuted/unresolved
        verified_at = T_n  ←  PREDICTION FINALIZED
        next_check_at = NULL

  (b) max_horizon < today_n, still no evidence
        scheduler runs force_unresolved_past_horizon(T_n)
        → bulk-update:
            status = UNRESOLVED
            verified_at = T_n
            evidence_text = "exceeded max_horizon"
        ←  PREDICTION FINALIZED (timeout fallback)
```

**Cost-per-prediction (envelope estimate):**

- LLM-cheap path: 1 verify call → terminal. Cost ≈ 1 × Opus call.
- Worst case: ~10 verifies (vague open-ended) → terminal або timeout. Cost ≈ 10 × Opus calls.
- Бюджетна оцінка: 1000 predictions × avg 2.5 verifies = 2500 Opus calls × ~3k tokens × $5/M input + $25/M output ≈ $40 на 1000 predictions on Opus.

---

## 3. Trigger logic — `get_eligible_for_verification(today, limit)`

Який саме SQL-фільтр застосовується кожний cycle.

```
                ┌──────────────────────────────────────────┐
                │ predictions table (PostgresPredictionDB) │
                │                                          │
                │  ┌────────┬───────┬────────┬───────────┐ │
                │  │ id     │status │verified│ next_     │ │
                │  │        │       │_at     │ check_at  │ │
                │  ├────────┼───────┼────────┼───────────┤ │
                │  │ p1     │UNRES  │ NULL   │ NULL      │ │  ←  fresh extracted
                │  │ p2     │UNRES  │ NULL   │ 2027-01   │ │  ←  in-flight, not yet ready
                │  │ p3     │UNRES  │ NULL   │ 2026-04   │ │  ←  in-flight, ready
                │  │ p4     │CONFIRM│2025-08 │ NULL      │ │  ←  terminal
                │  │ p5     │UNRES  │ NULL   │ NULL      │ │  ┐ also has
                │  │        │       │        │           │ │ │ max_horizon=
                │  │        │       │        │           │ │ │ 2025-12 — expired
                │  └────────┴───────┴────────┴───────────┘ │
                └──────────────────┬───────────────────────┘
                                   │
                                   │ today = 2026-04-29
                                   │
                                   ▼
        ┌─────────────────────────────────────────────────────┐
        │ get_eligible_for_verification(today=2026-04-29)     │
        │                                                     │
        │ SQL filter:                                         │
        │   WHERE verified_at IS NULL                         │
        │     AND (next_check_at IS NULL                      │
        │          OR next_check_at <= today)                 │
        │     AND (max_horizon IS NULL                        │
        │          OR max_horizon >= today)                   │
        │   LIMIT {batch_size}                                │
        └────────────────────┬────────────────────────────────┘
                             │
                             ▼
                     ┌───────────────────┐
                     │ Eligible: [p1,p3] │
                     │                   │
                     │ ❌ p2: next_check │
                     │   _at > today     │
                     │ ❌ p4: verified   │
                     │ ❌ p5: max_horiz  │
                     │   exceeded —      │
                     │   handled by      │
                     │   force_unresolv  │
                     │   ed_past_horizon │
                     │   instead         │
                     └───────────────────┘
```

**Index used:** `idx_predictions_eligible(verified_at, next_check_at, max_horizon)`. Composite index ensures O(log N) filter навіть при мільйоні rows.

---

## 4. Full verification cycle — orchestrator combining everything

Один запуск scheduler-cycle (Task 15 буде це викликати).

```
        ┌──────────────────┐
        │  Trigger Source  │
        │                  │
        │  cron / FastAPI  │
        │  endpoint /      │
        │  manual call     │
        └────────┬─────────┘
                 │
                 │ verification_cycle(today)
                 ▼
   ┌──────────────────────────────────────────────────────┐
   │                                                       │
   │  Step 1: HOUSEKEEPING                                 │
   │  ────────────────────────                             │
   │  n_finalized = pred_repo.                             │
   │      force_unresolved_past_horizon(today)             │
   │                                                       │
   │  ┌────────────────────────────────────────────┐       │
   │  │ UPDATE predictions                          │       │
   │  │ SET status='unresolved', verified_at=today, │       │
   │  │     evidence_text='exceeded max_horizon'    │       │
   │  │ WHERE verified_at IS NULL                   │       │
   │  │   AND max_horizon IS NOT NULL               │       │
   │  │   AND max_horizon < today                   │       │
   │  └────────────────────────────────────────────┘       │
   │                                                       │
   │  → Returns count of finalized rows (telemetry)        │
   │                                                       │
   └──────────────────────────┬────────────────────────────┘
                              │
                              ▼
   ┌──────────────────────────────────────────────────────┐
   │                                                       │
   │  Step 2: FETCH BATCH                                  │
   │  ────────────────                                     │
   │  eligible = pred_repo.                                │
   │      get_eligible_for_verification(today, limit=100)  │
   │                                                       │
   │  ┌────────────────────────────────────────────┐       │
   │  │ SELECT * FROM predictions                    │       │
   │  │ WHERE verified_at IS NULL                    │       │
   │  │   AND (next_check_at IS NULL OR ...)         │       │
   │  │   AND (max_horizon IS NULL OR ...)           │       │
   │  │ LIMIT 100                                    │       │
   │  └────────────────────────────────────────────┘       │
   │                                                       │
   │  → list[Prediction]  (up to 100)                      │
   │                                                       │
   └──────────────────────────┬────────────────────────────┘
                              │
                              │ for pred in eligible:
                              │
                              ▼
   ┌──────────────────────────────────────────────────────┐
   │                                                       │
   │  Step 3: VERIFY EACH (in series, rate-limited)        │
   │  ────────────────────────────────                     │
   │                                                       │
   │  for pred in eligible:                                │
   │     post_excerpt = doc_repo.get(pred.document_id)     │
   │                          .raw_text[:500]              │
   │                                                       │
   │     pred = await verifier.verify_v2(                  │
   │         pred, today=today, post_excerpt=excerpt       │
   │     )                                                 │
   │     # ↑ this mutates pred — see Diagram 1             │
   │                                                       │
   │     await pred_repo.update(pred)                      │
   │     # ↑ writes mutated state back                     │
   │                                                       │
   │     await asyncio.sleep(min_interval)                 │
   │     # ↑ rate-limit per Anthropic 30k ITPM             │
   │                                                       │
   └──────────────────────────┬────────────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ cycle complete      │
                   │ telemetry:          │
                   │   - n_finalized     │
                   │   - n_processed     │
                   │   - n_terminal      │
                   │   - n_premature     │
                   │   - n_errors        │
                   └─────────────────────┘
```

**Чому Step 1 ВПЕРЕД, не паралельно з Step 2:**
Якщо запустити одночасно — Step 2 може потягнути prediction з `max_horizon < today`, відправити його на Opus, отримати очікуване `unresolved`, і витратити LLM call даремно. Step 1 відсікає expired-horizon **до** будь-яких LLM-викликів.

---

## 5. v1 vs v2 — what changed

```
                   ┌─────────────────────┐
                   │  Verifier v1 (old)  │
                   └──────────┬──────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │ Input: prediction              │
              │  (no `today` param)            │
              │  (no post_excerpt)             │
              └────────────┬───────────────────┘
                           │
                           ▼
              ┌───────────────────────────────┐
              │ LLM call → 4-field response:   │
              │  • status: confirmed | refuted │
              │            | unresolved        │
              │  • confidence                  │
              │  • evidence_url                │
              │  • evidence_text               │
              └────────────┬───────────────────┘
                           │
                           ▼
              ┌───────────────────────────────┐
              │ ALWAYS terminal:               │
              │  • status set                  │
              │  • verified_at = NOW           │
              │  No retry semantics — every    │
              │  prediction gets a verdict     │
              │  immediately, even premature   │
              │  ones (which gives shitty      │
              │  unresolved).                  │
              └───────────────────────────────┘


                   ┌─────────────────────┐
                   │ Verifier v2 (new)   │
                   └──────────┬──────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │ Input: prediction, today,      │
              │        post_excerpt            │
              │  (today: critical for retry/   │
              │   horizon math)                │
              │  (post_excerpt: helps with     │
              │   conditional and context)     │
              └────────────┬───────────────────┘
                           │
                           ▼
              ┌───────────────────────────────┐
              │ LLM call → 7-field response:   │
              │  • status: confirmed | refuted │
              │            | unresolved        │
              │            | premature ★ NEW   │
              │  • confidence                  │
              │  • prediction_strength: low    │
              │            | medium | high ★   │
              │  • reasoning                   │
              │  • evidence (combined,         │
              │       URL or fact)             │
              │  • retry_after ★ NEW           │
              │  • max_horizon ★ NEW           │
              └────────────┬───────────────────┘
                           │
                           ▼
              ┌───────────────────────────────┐
              │ Two paths:                     │
              │                                │
              │ TERMINAL (3 statuses):         │
              │   • status set                 │
              │   • verified_at = today        │
              │   • next_check_at = NULL       │
              │                                │
              │ IN-FLIGHT (premature):         │
              │   • status stays UNRESOLVED    │
              │   • verified_at = NULL         │
              │   • next_check_at = retry_     │
              │     after                      │
              │   • returns to queue           │
              │                                │
              │ Set-once (regardless of path): │
              │   • prediction_strength        │
              │     (if not already set)       │
              │   • max_horizon                │
              │     (if not already set)       │
              │                                │
              │ Always:                        │
              │   • verify_attempts += 1       │
              └───────────────────────────────┘
```

### Що додалось у v2

| Feature | Чим розв'язує |
|---------|--------------|
| `premature` status | "wait, can't verify yet" — вирішує бідні `unresolved` для майбутніх подій |
| `prediction_strength` | track-record статистика — розрізняти high-quality від vague hedges |
| `max_horizon` | finite check window — не перевіряти "Зеленський втратить владу" 50 років |
| `retry_after` | дешевий retry-loop через `next_check_at` поле |
| `today` injection | LLM знає референс-дату, правильно judges retry/horizon |
| `post_excerpt` | для conditional ("якщо X") дає контекст коли X сталось |
| Mutual-exclusion in parser | відсікає Opus inconsistency (unresolved + retry_after) |

---

## Cross-references

- Spec: [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md)
- Implementation plan: [`2026-04-29-verification-trigger-policy-plan.md`](2026-04-29-verification-trigger-policy-plan.md)
- Architecture refresh (where Flow 5b lives): [`2026-04-26-architecture-current.md`](2026-04-26-architecture-current.md)
- v1 empirical baseline: `scripts/outputs/extraction_eval/verifier_4status_test.json`
