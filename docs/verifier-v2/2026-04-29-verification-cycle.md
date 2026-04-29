# Verification Cycle — Orchestrator Data Flow

**Дата:** 2026-04-29
**Status:** Reference (Task 15 буде це викликати)
**Spec:** [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md)

Один запуск scheduler-cycle: housekeeping → fetch batch → verify each. Це pseudo-orchestrator — реальний `verification_cycle()` буде написаний у Task 15.

---

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
        V-->>O: pred (mutated)
        O->>R: update(pred)
        R->>DB: UPDATE predictions SET ... WHERE id = ?
        Note over O: asyncio.sleep(min_interval)<br/>per Anthropic 30k ITPM
    end

    O-->>T: cycle telemetry<br/>{n_finalized, n_processed,<br/>n_terminal, n_premature, n_errors}
```

## Чому Step 1 ВПЕРЕД, не паралельно з Step 2

Якщо запустити одночасно — Step 2 може потягнути prediction з `max_horizon < today`, відправити його на Opus, отримати очікуване `unresolved`, і витратити LLM call даремно. Step 1 відсікає expired-horizon **до** будь-яких LLM-викликів.

Інша причина: Step 1 — це bulk SQL `UPDATE`, дешева операція. Step 3 — N × LLM-calls, дорого. Cleanup перед навантаженням → менше шансів зустріти "сміття" в фазі N×3.

## Telemetry

Cycle повертає 5 лічильників:

| Field | Meaning | Сигнал якщо аномально |
|-------|---------|----------------------|
| `n_finalized` | predictions закриті housekeeping'ом (max_horizon expired) | Якщо великий — verifier не справляється з premature за свій horizon |
| `n_processed` | predictions через verifier цього cycle | Telemetry на cycle throughput |
| `n_terminal` | з n_processed: ті що отримали final verdict | Higher = better |
| `n_premature` | з n_processed: ті що повернулись у чергу з `next_check_at` | Higher = vague predictions переважають |
| `n_errors` | LLM/parse-failures (`verify_attempts++` only) | Будь-яка ненульова цифра — alert |

---

## Cross-references

- Single verify_v2 call (Step 3 деталі): [`2026-04-29-verifier-v2-call.md`](2026-04-29-verifier-v2-call.md)
- Як cycle переводить prediction між станами: [`2026-04-29-prediction-lifecycle.md`](2026-04-29-prediction-lifecycle.md)
- Spec: [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md)
- Implementation plan: [`2026-04-29-verification-trigger-policy-plan.md`](2026-04-29-verification-trigger-policy-plan.md)
