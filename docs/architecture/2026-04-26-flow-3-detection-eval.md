# Flow 3: Detection Eval (Task 13)

**Дата:** 2026-04-26
**Status:** ✅ implemented (Task 13 done, winner picked)
**Index:** [`2026-04-26-architecture-current.md`](2026-04-26-architecture-current.md)

Бенчмарк YES/NO детекції на gold-розмічених постах. 5 моделей × 2 промптові версії → P/R/F1 матриця → вибір production-моделі.

**Тригер:** ручний (запускається при появі нового кандидата на production-модель).

---

```mermaid
flowchart TD
    Gold[("data/gold_labels.json<br/>(~130 entries)")]:::store
    Sample[("data/sample_posts.json<br/>(1049 posts)")]:::store
    Join["Inner-join по id<br/>→ ~130 анотованих постів"]:::step

    Script["scripts/evaluate_detection.py<br/>run_evaluation_for_model()"]:::script

    M1["claude-haiku-4-5"]:::model
    M2["deepseek-chat"]:::model
    M3["gemini-3.1-flash-lite-preview ⭐"]:::winner
    M4["gpt-5-mini"]:::model
    M5["llama-3.3-70b"]:::model

    Versions["× 2 prompt versions<br/>(v1 baseline + v2 refined)<br/>= 10 (model, prompt) pairs"]:::step

    Loop["For each pair:<br/>for each post: LLM call → YES/NO<br/>compare with gold → TP/FP/FN/TN"]:::step
    Aggregate["Aggregate: P/R/F1 +<br/>per-error-bucket breakdown"]:::step

    Out[("outputs/detection_eval/<br/>detection_results_&lt;provider&gt;_<br/>&lt;model&gt;[_v1_baseline].json<br/>(10 files)")]:::store

    Winner[/"WINNER:<br/>gemini-3.1-flash-lite-preview<br/>F1 = 0.848<br/>(precision 0.79, recall 0.92)"/]:::winnerOut

    Gold --> Join
    Sample --> Join
    Join --> Script
    Script --> M1
    Script --> M2
    Script --> M3
    Script --> M4
    Script --> M5
    M1 --> Versions
    M2 --> Versions
    M3 --> Versions
    M4 --> Versions
    M5 --> Versions
    Versions --> Loop
    Loop --> Aggregate
    Aggregate --> Out
    Out --> Winner

    classDef store fill:#1a4a2a,stroke:#88ff88,color:#fff
    classDef script fill:#2a3a55,stroke:#88c5ff,color:#fff
    classDef step fill:#1a3550,stroke:#88c5ff,color:#fff
    classDef model fill:#3a3a55,stroke:#aaccff,color:#fff
    classDef winner fill:#007744,stroke:#fff,color:#fff,stroke-width:3px
    classDef winnerOut fill:#005544,stroke:#fff,color:#fff,stroke-width:2px
```

## Output schema

```json
{
  "model_id": "...",
  "prompt_version": "v1|v2",
  "n_pos": 0, "n_neg": 0,
  "tp": 0, "fp": 0, "fn": 0, "tn": 0,
  "precision": 0.0, "recall": 0.0, "f1": 0.0,
  "errors": [{"post_id": "...", "label": "YES|NO", "predicted": "YES|NO", ...}]
}
```

## Передбачення наступного запуску

При додаванні нової моделі (наприклад `gemini-3.1-pro`, `claude-opus-4-6`) — кожен запуск перетирає `detection_results_<model>.json` своєю версією. `*_v1_baseline.json` залишається як reference точка.

---

## Cross-references

- Inputs: [`2026-04-26-flow-2-gold-annotation.md`](2026-04-26-flow-2-gold-annotation.md), [`2026-04-26-flow-1-telegram-collection.md`](2026-04-26-flow-1-telegram-collection.md)
- Майбутнє виносу `Detector` в production: [`2026-04-26-flow-production-ingestion.md`](2026-04-26-flow-production-ingestion.md)
- Index: [`2026-04-26-architecture-current.md`](2026-04-26-architecture-current.md)
