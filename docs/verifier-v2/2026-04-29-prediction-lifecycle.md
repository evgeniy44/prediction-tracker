# Prediction Lifecycle — State Machine

**Дата:** 2026-04-29
**Status:** Reference
**Spec:** [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md)

Стани, через які проходить ОДНА `Prediction` від моменту створення (extraction) до terminal verdict. Цикл може містити кілька викликів verifier'а — між ними prediction "спить" у БД до настання `next_check_at`.

---

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

## Cost-per-prediction (envelope estimate)

- **Cheap path:** 1 verify call → terminal. Cost ≈ 1 × Opus call.
- **Worst case:** ~10 verifies (vague open-ended) → terminal або timeout. Cost ≈ 10 × Opus calls.
- **Бюджетна оцінка:** 1000 predictions × avg 2.5 verifies = 2500 Opus calls × ~3k tokens × ($5 / 1M input + $25 / 1M output) ≈ **$40 на 1000 predictions** на Opus 4.6.

## Чому `PREMATURE` НЕ persisted у `status`

`InFlight` стан описується **комбінацією** полів: `status=UNRESOLVED AND verified_at=NULL AND next_check_at IS NOT NULL`. Окремий enum-value `PREMATURE` не потрібен — він би дублював інформацію в `next_check_at`. Це дозволяє єдиний trigger filter для черги (`get_eligible_for_verification`, див. [verification-cycle doc](2026-04-29-verification-cycle.md)).

---

## Cross-references

- Single verify_v2 call (один перехід state machine): [`2026-04-29-verifier-v2-call.md`](2026-04-29-verifier-v2-call.md)
- Full orchestration cycle (включно з SQL-фільтром eligible): [`2026-04-29-verification-cycle.md`](2026-04-29-verification-cycle.md)
- Spec: [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md)
