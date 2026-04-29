# Flow 2: Gold Annotation

**Дата:** 2026-04-26
**Status:** ✅ implemented (manual + commit-based)
**Index:** [`2026-04-26-architecture-current.md`](2026-04-26-architecture-current.md)

Ручна розмітка постів YES/NO для evals. Це фундамент Flow 3 і Flow 4 (без gold-міток evaluator не може порахувати precision/recall).

**Тригер:** ручний (1-2 рази; розширюється коли треба покрити нові edge cases).

---

```mermaid
flowchart TD
    Sample[("data/sample_posts.json<br/>1049 posts:<br/>Арестович + Гордон + Подоляк")]:::store
    Guidelines[("docs/annotation/<br/>annotation-guidelines.md<br/>YES/NO rubric +<br/>7 anti-patterns")]:::guideline
    Human["👤 Людина читає по черзі"]:::human
    Decision{{"Чи містить пост<br/>передбачення?"}}:::decision
    Yes["YES — додає до gold<br/>з has_prediction=true"]:::yes
    No["NO — додає до gold<br/>з has_prediction=false"]:::no
    Gold[("data/gold_labels.json<br/>schema: [{id, has_prediction}]<br/><br/>130 entries:<br/>97 Арестович (15 YES + 82 NO)<br/>+ 16 Подоляк + 17 інші")]:::store

    Sample --> Human
    Guidelines --> Human
    Human --> Decision
    Decision --> Yes
    Decision --> No
    Yes --> Gold
    No --> Gold

    classDef store fill:#1a4a2a,stroke:#88ff88,color:#fff
    classDef guideline fill:#3a3a55,stroke:#aaccff,color:#fff
    classDef human fill:#553300,stroke:#fff,color:#fff
    classDef decision fill:#1a3550,stroke:#88c5ff,color:#fff
    classDef yes fill:#007744,stroke:#fff,color:#fff
    classDef no fill:#aa2222,stroke:#fff,color:#fff
```

## Implementation note

**Жодного скрипта-помічника** в репозиторії немає — `gold_labels.json` створювався вручну (terminal interaction в окремих сесіях, фіксувався як commit).

Послідовність:
- Task 12 початково на 50 постах (commit `428aea4`)
- Розширення до 130 (commit `a992e0f`)

## Споживачі цих даних

- **Flow 3** (Detection eval): порівнює модель's YES/NO з gold для P/R/F1
- **Flow 4** (Extraction quality eval): використовує `has_prediction=true` як trigger to validate що модель щось витягнула

---

## Cross-references

- Annotation rubric: [`../annotation/annotation-guidelines.md`](../annotation/annotation-guidelines.md)
- Споживачі: [`2026-04-26-flow-3-detection-eval.md`](2026-04-26-flow-3-detection-eval.md), [`2026-04-26-flow-4-extraction-quality-eval.md`](2026-04-26-flow-4-extraction-quality-eval.md)
- Index: [`2026-04-26-architecture-current.md`](2026-04-26-architecture-current.md)
