# Task 19.8d — `situation` field (replaces verbatim `context`)

**Status:** draft 2026-05-14
**Task:** 19.8d (replace verbatim context з model-paraphrase situation)
**Prerequisites:** ✅ Task 19.8a (context field), ✅ Task 19.8c (extractor context wiring)
**Impacts:** Task 19.8b (re-run extraction needed — новий field), Task 19.7b (gold matиме situation)

---

## TL;DR

Емпіричне review V2 extraction (32 claims) показало що verbatim `context` низькоцінний:
- TOC/agenda пости — context це рядок тайм-коду, не пояснення
- Prose пости — situational setup non-contiguous з claim, verbatim-substring не охоплює обидва

Рішення: **замінити `context` на `situation`** — model-paraphrase (1-2 речення) що пояснює "у відповідь на яку ситуацію/події автор зробив прогноз". REQUIRED, validated by presence (non-empty), drop prediction якщо відсутнє. Verbatim substring validation видаляється.

**Це rename context → situation наскрізь** (Pydantic, DB, prompts, extractor, verifier) + зміна validation з substring на presence.

---

## Architectural decisions

| # | Рішення | Обґрунтування |
|---|---|---|
| Q1 | **situation REPLACES context** (rename, не додаткове поле) | Verbatim context емпірично шум (рестейтмент claim / TOC рядок). Один корисний field краще за два де один noise. YAGNI. |
| Q2 | **situation = model paraphrase** (NON-verbatim, 1-2 речення) | Охоплює non-contiguous setup + TOC themes що verbatim не може. Реальний disambiguation для verifier. |
| Q3 | **REQUIRED, presence validation** (non-empty), drop on missing | Quality gate зберігається, інший критерій: "чи модель сформулювала ситуацію?". Природно відсіює TOC-claims (модель не артикулює situation для пункту змісту). |
| Q4 | **Видалити substring validation** (`validate_context_in_post`) | N/A для paraphrase. Anti-hallucination зміщується на Opus judge + human gold labeling. situation — grounded summary (low hallucination risk). |
| Q5 | **Verifier label updated** | VERIFICATION_TEMPLATE_V2: `{post_excerpt}` → `{situation}`, label "Original post excerpt" → "Situation that prompted the claim". Чесна semantics. |
| Q6 | **Rename mechanics** (не drop+add) | Prod даних немає. Rename Prediction field + DB column (alter_column) + усі usages. Чиста semantics. |

---

## Trade-off (свідомий)

**Втрачаємо:** substring anti-hallucination gate (drop на вигадану цитату).

**Compensated by:**
1. Opus judge (Task 13.5) оцінює extraction quality
2. Human gold labeling переглядає кожен claim проти посту — situation hallucination спіймається вручну
3. situation — це summary прочитаного посту (grounded), не fabrication про зовнішній світ → low risk

---

## Schema changes (rename context → situation)

### Domain (`src/prophet_checker/models/domain.py`)

```python
class Prediction(BaseModel):
    id: str
    document_id: str
    person_id: str
    claim_text: str
    situation: str | None = None     # було: context
    prediction_date: date
    ...
```

### DB (`src/prophet_checker/models/db.py`)

```python
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    situation: Mapped[str | None] = mapped_column(Text, nullable=True)   # було: context
```

### Mappers (`src/prophet_checker/storage/postgres.py`)

`domain_to_prediction_db`: `situation=pred.situation` (було context=pred.context)
`prediction_db_to_domain`: `situation=db.situation` (було context=db.context)

### Alembic migration

`alembic/versions/<rev>_rename_context_to_situation.py`:

```python
revision = '<rev>'
down_revision = '2c09afbbdcdf'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.alter_column("predictions", "context", new_column_name="situation")

def downgrade() -> None:
    op.alter_column("predictions", "situation", new_column_name="context")
```

---

## Prompt changes (`src/prophet_checker/llm/prompts.py`)

### EXTRACTION_TEMPLATE — context field → situation field

Замінити bullet:
```
- context: VERBATIM quote from the post (~300 chars max) that
  shows what the claim refers to...
```
на:
```
- situation: 1-2 sentences (in the post's language) summarizing the
  events or circumstances the author was responding to when making
  this prediction. Answer "in response to what situation was this
  forecast made?". Synthesize from the whole post — capture preceding
  setup, triggering events, persons involved. This is YOUR summary,
  NOT a verbatim quote.
```

JSON shape: `{{"claim_text": "...", "prediction_date": "...", "target_date": "...", "topic": "...", "situation": "..."}}`

### validate_context_in_post → validate_situation

Видалити `validate_context_in_post` (substring). Додати:
```python
def validate_situation(situation: str | None) -> bool:
    return bool(situation and situation.strip())
```

### build_verification_prompt_v2 — context kwarg → situation kwarg

```python
def build_verification_prompt_v2(
    claim: str,
    prediction_date: str,
    target_date: str | None,
    today: str,
    situation: str,
) -> str:
    return VERIFICATION_TEMPLATE_V2.format(
        claim=claim,
        prediction_date=prediction_date,
        target_date=target_date or "not specified",
        today=today,
        situation=situation,
    )
```

### VERIFICATION_TEMPLATE_V2 — placeholder + label

Замінити блок:
```
Original post excerpt (for context):
---
{post_excerpt}
---
```
на:
```
Situation that prompted the claim:
---
{situation}
---
```

---

## Extractor changes (`src/prophet_checker/analysis/extractor.py`)

```python
from prophet_checker.llm.prompts import (
    build_extraction_prompt,
    get_extraction_system,
    parse_extraction_response,
    validate_situation,           # було: validate_context_in_post
)

# у loop, після claim non-empty check:
            situation = raw.get("situation")
            if not validate_situation(situation):
                logger.warning(
                    "Drop prediction — missing/empty situation: %r", claim[:60]
                )
                continue

# у Prediction(...):
                    claim_text=claim,
                    situation=situation,        # було: context=context
```

Зауваж: `validate_situation(situation)` НЕ потребує `text` param (presence-only, не substring). Сигнатура extract() незмінна (text досі param, просто не передається у validate).

---

## Re-run impact

Після 19.8d landed:
- Existing `scripts/outputs/verification_eval/v2_extraction_outputs.json` **invalidated** (має старий context field, не situation). Re-run Task 19.8b Stage 1 (`v2_extraction_run.py`) знову — отримати situation замість context.
- `scripts/v2_extraction_run.py` `serialize_v2_prediction`: `context` → `situation` (1-рядкова зміна — частина 19.8d або 19.8b re-run prep).

19.8b plan вже revised (post-19.8c) — потребує другого touch: `serialize_v2_prediction` field rename. Невелике.

---

## Files affected

**Modify:**
- `src/prophet_checker/models/domain.py` — Prediction.context → situation
- `src/prophet_checker/models/db.py` — PredictionDB.context → situation
- `src/prophet_checker/storage/postgres.py` — mappers
- `src/prophet_checker/llm/prompts.py` — EXTRACTION_TEMPLATE, validate_context_in_post→validate_situation, build_verification_prompt_v2, VERIFICATION_TEMPLATE_V2
- `src/prophet_checker/analysis/extractor.py` — import, validation, field
- `scripts/v2_extraction_run.py` — serialize_v2_prediction field rename
- `tests/test_models.py` — context test → situation
- `tests/test_storage_postgres.py` — mapper tests context → situation
- `tests/test_llm_prompts.py` — remove 4 validate_context tests, add validate_situation tests, EXTRACTION_TEMPLATE test, build_verification_prompt_v2 test
- `tests/test_analysis_extractor.py` — fixture + drop tests context → situation
- `docs/verification-track/2026-05-14-task-19-8b-v2-extraction-rerun-plan.md` — serialize field note

**Create:**
- `alembic/versions/<rev>_rename_context_to_situation.py`

**Down_revision chain:**
```
edb2e385f26b → 30fd925789cb → 8df4e2013c5a → 2c09afbbdcdf → <rev (rename)>
```

---

## Tests delta

| Area | Change |
|---|---|
| test_models | `test_prediction_has_context_field_default` → `test_prediction_has_situation_field_default` |
| test_storage_postgres | 2 mapper tests context → situation |
| test_llm_prompts | Remove 4 `validate_context_in_post` tests; add ~3 `validate_situation` tests (non-empty True, empty False, whitespace-only False, None False); update EXTRACTION_TEMPLATE test (situation instruction present); update build_verification_prompt_v2 test (situation kwarg) |
| test_analysis_extractor | Fixture `LLM_RESPONSE_ONE` context→situation; `test_extract_returns_predictions` assert p.situation; drop tests: hallucinated-context → drop-on-missing-situation (substring test видаляється бо presence-only) |
| test_alembic | New `test_rename_context_migration_loads_cleanly` (down_revision 2c09afbbdcdf) |

**Net test count:** приблизно нейтрально (видаляємо 4 substring tests, додаємо ~3 presence tests + 1 migration). Estimate: 154 → ~153-154 (мінус 1-2). Точна цифра у плані.

---

## Out of scope

- ❌ Re-run Task 19.8b extraction (operational, окремо після 19.8d landed)
- ❌ Keeping verbatim context as secondary field (replace, not supplement)
- ❌ situation content validation beyond non-empty (no length/semantic checks)
- ❌ Re-run Task 13/13.5
- ❌ Production orchestrator (Task 20)

---

## Open question для review

**Чи зберігати `validate_situation` як named function** чи inline `if not (situation and situation.strip())`? Spec пропонує named function (testable, consistent з patterns). Якщо вважаєш overkill для presence check — можна inline.

---

## Cross-references

- **19.8a (context field):** `../2026-05-14-task-19-8a-extraction-context-schema-design.md`
- **19.8c (extractor wiring):** `../2026-05-14-task-19-8c-extractor-context-wiring-design.md`
- **19.8b (V2 run):** `../2026-05-14-task-19-8b-v2-extraction-rerun-design.md`
- **Empirical trigger:** v2_extraction_outputs.json contextReview annotations (1395, 1585, 1779, 2899)
