# Verifier v2 — Data Flow Diagrams

**Дата:** 2026-04-29
**Доповнює:** [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md) (the spec)
**Статус:** Reference visualization — for understanding, not implementation gate

5 візуалізацій Verifier v2 у форматі Mermaid (рендериться у GitHub, GitLab, Obsidian out-of-the-box). Спершу читай spec для контексту; ці діаграми — для швидкого огляду «як воно тече».

---

## 1. Single verification call — `verify_v2(prediction, today, post_excerpt)`

Що відбувається у момент виклику verifier'а на ОДНУ prediction.

```mermaid
sequenceDiagram
    autonumber
    participant C as Caller (orchestrator)
    participant V as PredictionVerifier
    participant P as build_prompt_v2
    participant L as LLMClient (Opus)
    participant R as parse_response_v2
    participant DB as Prediction state

    C->>V: verify_v2(prediction, today, post_excerpt)
    V->>DB: verify_attempts += 1
    V->>P: build user + system prompts
    P-->>V: (user, system) text
    V->>L: complete(prompt, system)

    alt LLM success
        L-->>V: raw JSON response
        V->>R: parse_verification_response_v2(raw)

        alt Parse OK and not invalid
            R-->>V: VerificationResult

            opt prediction_strength is None
                V->>DB: set prediction_strength (set-once)
            end
            opt max_horizon is None and result has it
                V->>DB: set max_horizon (set-once)
            end

            alt status == "premature"
                V->>DB: next_check_at = result.retry_after
                Note over DB: stays in queue<br/>verified_at = NULL
            else status terminal (C/R/U)
                V->>DB: status, confidence, evidence
                V->>DB: verified_at = today
                V->>DB: next_check_at = NULL
            end

        else Parse fail or verdict_invalid
            R-->>V: None / invalid
            Note over V,DB: only verify_attempts++ persists
        end

    else LLM exception
        L-->>V: Exception (logged)
        Note over V,DB: only verify_attempts++ persists
    end

    V-->>C: prediction (mutated)
```

**Інваріанти, які тримаються:**

- `verify_attempts` ВЖЕ ЗБІЛЬШЕНО, навіть якщо все інше провалилось.
- `prediction_strength` і `max_horizon` встановлюються **раз** (set-once); подальші виклики їх не переписують.
- `next_check_at` і `verified_at` — взаємно виключаючі: in-flight prediction має `next_check_at != NULL AND verified_at = NULL`; terminal — навпаки.

---

## 2. Lifecycle of a Prediction — multiple verifications over time

Стани, через які проходить ОДНА prediction від моменту створення (extraction) до terminal verdict.

```mermaid
stateDiagram-v2
    [*] --> Extracted: Task 15 orchestrator<br/>creates Prediction

    Extracted --> InFlight: verify_v2 → "premature"<br/>(set strength + max_horizon<br/>+ next_check_at)
    Extracted --> Terminal: verify_v2 → C/R/U<br/>(set strength + verified_at)

    InFlight --> InFlight: next_check_at ≤ today<br/>still "premature"<br/>(set-once fields preserved)
    InFlight --> Terminal: verifier finds evidence<br/>OR confirms ambiguity
    InFlight --> ForcedTerminal: max_horizon < today<br/>(force_unresolved_past_horizon)

    Terminal --> [*]: persisted final
    ForcedTerminal --> [*]: persisted as<br/>UNRESOLVED + evidence=<br/>"exceeded max_horizon"

    note right of Extracted
        status=UNRESOLVED (default)
        verified_at=NULL
        next_check_at=NULL
        prediction_strength=NULL
        max_horizon=NULL
        verify_attempts=0
    end note

    note right of InFlight
        status=UNRESOLVED (unchanged)
        verified_at=NULL
        next_check_at=YYYY-MM-DD
        prediction_strength=set (e.g. "medium")
        max_horizon=set or NULL
        verify_attempts=N
    end note

    note right of Terminal
        status=confirmed/refuted/unresolved
        verified_at=today
        next_check_at=NULL
        evidence_text=concrete fact
        prediction_strength=set
    end note
```

**Cost-per-prediction (envelope estimate):**

- Cheap path: 1 verify call → terminal. Cost ≈ 1 × Opus call.
- Worst case: ~10 verifies (vague open-ended) → terminal або timeout. Cost ≈ 10 × Opus calls.
- Бюджетна оцінка: 1000 predictions × avg 2.5 verifies = 2500 Opus calls × ~3k tokens × ($5 / 1M input + $25 / 1M output) ≈ $40 на 1000 predictions on Opus.

---

## 3. Trigger logic — `get_eligible_for_verification(today, limit)`

Який саме фільтр SQL застосовується кожний cycle.

```mermaid
flowchart TD
    Start([predictions table]) --> F1{verified_at<br/>IS NULL?}
    F1 -- No --> Skip1[❌ Already terminal<br/>skip]
    F1 -- Yes --> F2{next_check_at IS NULL<br/>OR &lt;= today?}
    F2 -- No --> Skip2[❌ Too early<br/>skip until next_check_at]
    F2 -- Yes --> F3{max_horizon IS NULL<br/>OR &gt;= today?}
    F3 -- No --> Skip3[⚠️ Expired<br/>handled by<br/>force_unresolved_past_horizon<br/>not eligible queue]
    F3 -- Yes --> Eligible([✅ ELIGIBLE<br/>included in batch])

    style Skip1 fill:#ffe6e6
    style Skip2 fill:#fff4e6
    style Skip3 fill:#fff4e6
    style Eligible fill:#e6ffe6
```

**Приклад того як фільтр застосовується до 5 різних predictions** (today = 2026-04-29):

| id | status | verified_at | next_check_at | max_horizon | Verdict |
|----|--------|-------------|---------------|-------------|---------|
| p1 | UNRES | NULL | NULL | NULL | ✅ eligible (fresh extracted) |
| p2 | UNRES | NULL | 2027-01-01 | NULL | ❌ next_check_at > today |
| p3 | UNRES | NULL | 2026-04-01 | NULL | ✅ eligible (next_check_at passed) |
| p4 | CONFIRM | 2025-08-15 | NULL | NULL | ❌ already terminal |
| p5 | UNRES | NULL | NULL | 2025-12-31 | ⚠️ horizon exceeded — handled by housekeeping |

**Index used:** `idx_predictions_eligible(verified_at, next_check_at, max_horizon)`. Composite index ensures O(log N) filter навіть при мільйоні rows.

---

## 4. Full verification cycle — orchestrator combining everything

Один запуск scheduler-cycle (Task 15 буде це викликати).

```mermaid
sequenceDiagram
    autonumber
    participant T as Trigger (cron/FastAPI/CLI)
    participant O as Orchestrator
    participant R as PredictionRepo
    participant DR as DocumentRepo
    participant V as PredictionVerifier
    participant L as LLM (Opus)
    participant DB as Postgres

    T->>O: verification_cycle(today)

    Note over O,R: Step 1: Housekeeping (before any LLM call)
    O->>R: force_unresolved_past_horizon(today)
    R->>DB: UPDATE predictions<br/>SET status='unresolved', verified_at=today,<br/>evidence='exceeded max_horizon'<br/>WHERE max_horizon < today AND verified_at IS NULL
    DB-->>R: n_updated rows
    R-->>O: n_finalized (telemetry)

    Note over O,R: Step 2: Fetch batch
    O->>R: get_eligible_for_verification(today, limit=100)
    R->>DB: SELECT * FROM predictions<br/>WHERE verified_at IS NULL<br/>AND (next_check_at IS NULL OR <= today)<br/>AND (max_horizon IS NULL OR >= today)<br/>LIMIT 100
    DB-->>R: rows
    R-->>O: list[Prediction]

    Note over O,V: Step 3: Verify each (rate-limited)
    loop for each pred in eligible
        O->>DR: get_document_by_id(pred.document_id)
        DR-->>O: doc.raw_text
        O->>V: verify_v2(pred, today, post_excerpt=raw_text[:500])
        V->>L: complete(prompt, system)
        L-->>V: raw JSON response
        V-->>O: pred (mutated, see Diagram 1)
        O->>R: update(pred)
        R->>DB: UPDATE predictions SET ... WHERE id = ?
        Note over O: asyncio.sleep(min_interval)<br/>per Anthropic 30k ITPM
    end

    O-->>T: cycle telemetry<br/>{n_finalized, n_processed,<br/>n_terminal, n_premature, n_errors}
```

**Чому Step 1 ВПЕРЕД, не паралельно з Step 2:**
Якщо запустити одночасно — Step 2 може потягнути prediction з `max_horizon < today`, відправити його на Opus, отримати очікуване `unresolved`, і витратити LLM call даремно. Step 1 відсікає expired-horizon **до** будь-яких LLM-викликів.

---

## 5. v1 vs v2 — what changed

### Old verifier (v1) — single-shot, 4-field output

```mermaid
sequenceDiagram
    participant C as Caller
    participant V as PredictionVerifier (v1)
    participant L as LLM
    participant DB as Prediction

    C->>V: verify(prediction)
    Note right of V: NO `today` param<br/>NO post_excerpt
    V->>L: complete(prompt, system)
    L-->>V: 4-field JSON<br/>(status, confidence,<br/>evidence_url, evidence_text)
    V->>DB: ALWAYS terminal<br/>status set<br/>verified_at = NOW
    V-->>C: prediction (verified)
    Note over V,DB: No retry semantics —<br/>premature → unresolved (lossy)
```

### New verifier (v2) — supports retry-loop, 7-field output

```mermaid
sequenceDiagram
    participant C as Caller
    participant V as PredictionVerifier (v2)
    participant L as LLM
    participant DB as Prediction

    C->>V: verify_v2(prediction, today, post_excerpt)
    Note right of V: today injected<br/>post_excerpt for context
    V->>L: complete(v2_prompt, v2_system)
    L-->>V: 7-field JSON<br/>(status: C/R/U/premature,<br/>confidence,<br/>prediction_strength,<br/>reasoning, evidence,<br/>retry_after, max_horizon)

    alt status == "premature"
        V->>DB: next_check_at = retry_after<br/>set strength + max_horizon (once)
        Note over V,DB: stays in queue
    else terminal (C/R/U)
        V->>DB: verified_at = today<br/>set strength (once)
    end

    V-->>C: prediction (mutated)
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
- Architecture refresh (where Flow 5b lives): [`../architecture/2026-04-26-architecture-current.md`](../architecture/2026-04-26-architecture-current.md)
- v1 empirical baseline: `scripts/outputs/extraction_eval/verifier_4status_test.json`
