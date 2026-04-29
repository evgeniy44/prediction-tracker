# Verifier v2 — Single Call Data Flow

**Дата:** 2026-04-29
**Status:** Reference
**Spec:** [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md)

Що відбувається у момент виклику `verifier.verify_v2(prediction, today, post_excerpt)` на ОДНУ prediction. Дві діаграми: happy path + failure modes (вони симетричні — навмисно).

---

## 1a. Happy path (LLM ok, parse ok)

Лінійний flow без branching: caller → verifier → prompt → LLM → parser → mutation → return. Єдиний `alt` у кінці — terminal vs premature (це ключове рішення verifier'а).

```mermaid
sequenceDiagram
    autonumber
    participant C as Caller
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
    L-->>V: raw JSON response
    V->>R: parse_verification_response_v2(raw)
    R-->>V: VerificationResult

    Note over V,DB: Set-once metadata<br/>(only if currently NULL):<br/>prediction_strength, max_horizon

    Note over V,DB: ── path 1 of 2: status == "premature" ──
    rect rgba(255, 165, 0, 0.45)
        V->>DB: next_check_at = retry_after<br/>verified_at stays NULL → re-queue
    end

    Note over V,DB: ── path 2 of 2: status terminal (confirmed/refuted/unresolved) ──
    rect rgba(60, 200, 110, 0.45)
        V->>DB: status, confidence, evidence_text<br/>verified_at = today<br/>next_check_at = NULL
    end

    V-->>C: prediction (mutated — exactly ONE of paths 1/2 executes)
```

## 1b. Failure modes — symmetric early-return

При LLM-exception або parse-failure verifier поводиться однаково — це навмисна симетрія. Тільки `verify_attempts++` персиститься; решта state не торкається. Prediction лишається в queue, наступний cycle спробує знову.

```mermaid
sequenceDiagram
    autonumber
    participant C as Caller
    participant V as PredictionVerifier
    participant L as LLMClient (Opus)
    participant R as parse_response_v2
    participant DB as Prediction state

    C->>V: verify_v2(prediction, today, post_excerpt)
    V->>DB: verify_attempts += 1
    V->>L: complete(prompt, system)

    Note over V,L: ── failure path A: LLM call raises Exception ──
    rect rgba(220, 50, 50, 0.45)
        L-->>V: Exception (caught, logged)
    end

    Note over V,R: ── failure path B (alternative): parse fails or verdict_invalid ──
    rect rgba(220, 50, 50, 0.45)
        L-->>V: raw JSON response
        V->>R: parse_verification_response_v2(raw)
        R-->>V: None or VerificationResult(verdict_invalid=True)
    end

    Note over V,DB: NO mutation of status/verdict/<br/>strength/horizon/check_at.<br/>Only verify_attempts++ persists.<br/>Prediction stays in queue<br/>(next cycle will retry).

    V-->>C: prediction (only verify_attempts changed —<br/>path A or B reaches this same end-state)
```

## Інваріанти

- `verify_attempts` ВЖЕ ЗБІЛЬШЕНО, навіть якщо все інше провалилось (Diagram 1b).
- `prediction_strength` і `max_horizon` встановлюються **раз** (set-once); подальші виклики не переписують.
- `next_check_at` і `verified_at` — взаємно виключаючі: in-flight prediction має `next_check_at != NULL AND verified_at = NULL`; terminal — навпаки.

---

## Cross-references

- Lifecycle ОДНІЄЇ prediction через серію `verify_v2()` дзвінків: [`2026-04-29-prediction-lifecycle.md`](2026-04-29-prediction-lifecycle.md)
- Як verifier викликається з orchestrator'а: [`2026-04-29-verification-cycle.md`](2026-04-29-verification-cycle.md)
- Spec: [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md)
- Implementation plan: [`2026-04-29-verification-trigger-policy-plan.md`](2026-04-29-verification-trigger-policy-plan.md)
