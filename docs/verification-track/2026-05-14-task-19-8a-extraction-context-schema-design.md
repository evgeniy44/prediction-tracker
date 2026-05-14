# Task 19.8a — Extraction Context Field Schema + Prompt

**Status:** draft 2026-05-14
**Task:** 19.8a (extraction V2 contract — schema + prompt + parser + validator)
**Prerequisites:** ✅ Task 19.5 (V2 verification foundations), ✅ Task 19.7a (gold dataset)
**Sibling task:** Task 19.8b — re-run Gemini Flash Lite extraction + quality re-eval + manual context review (brainstorm next)
**Downstream:** Task 19.7b verification eval (waits for 19.8b backfilled gold)

---

## TL;DR

Розширити extraction output одним новим полем `context` per claim. Модель видає **verbatim quote з посту (~300 chars)**, що пояснює про що саме йде claim. Це поле зберігається у `Prediction` (Pydantic + DB), потрапляє у verifier prompt замість `post_excerpt`. Post-processing **validate** що context — справжній substring посту (substring після whitespace normalize). На fail — drop prediction з warning.

**Why:** наївний "перші 500 chars" часом не містить claim або релевантного контексту. Модель, що бачить весь пост, видає focused, claim-relevant snippet — менший token cost при verification + більш relevant disambiguation.

---

## Architectural decisions

| # | Рішення | Обґрунтування |
|---|---|---|
| Q1 | **Extraction output field** (одним викликом разом з claim) | Модель уже бачить весь пост — додавання context коштує мінімум tokens, проти окремого enrichment stage з 2 викликами |
| Q2 | **Verbatim quote ~300 chars** | Hallucination risk = 0 (модель вибирає, не пише). Verifier бачить реальний текст автора. |
| Q3 | **Substring validation у post-processing** | LLM погано рахують символи й offsets — програмний `context in raw_post` після whitespace normalize надійніший. |
| Q4 | **Заміна `post_excerpt` у verifier** | Один source of truth. Verifier API: `build_verification_prompt_v2(claim, ..., context)`. |
| Q5 | **Per-claim context** | Multi-claim пости (3 claims з одного посту 1779) — кожен claim має власний focused snippet. |
| Q6 | **Schema location: `Prediction.context`** | Одна колонка nullable у `predictions`. Без окремої таблиці. |
| Q7 | **Validation fail: drop з warning** | Hard режим — кращe втратити prediction, ніж заповнити DB галюцинаціями. Logger.warning + count в run summary. |

---

## Schema changes

### Domain (`src/prophet_checker/models/domain.py`)

```python
class Prediction(BaseModel):
    id: str
    document_id: str
    person_id: str
    claim_text: str
    context: str | None = None         # <-- NEW: verbatim post quote
    prediction_date: date
    target_date: date | None = None
    ... (existing fields unchanged)
```

`Nullable` бо існуючі legacy predictions (якщо колись зʼявляться) не мають context.

### DB (`src/prophet_checker/models/db.py`)

```python
class PredictionDB(Base):
    __tablename__ = "predictions"
    ...
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)  # NEW
    prediction_date: Mapped[date] = mapped_column(Date, nullable=False)
    ...
```

Розташування — одразу після `claim_text` (логічна пара).

### Mappers (`src/prophet_checker/storage/postgres.py`)

`domain_to_prediction_db`: `context=pred.context`
`prediction_db_to_domain`: `context=db.context`

### Alembic migration

`alembic/versions/<rev>_add_prediction_context.py`:

```python
revision = '<new>'
down_revision = '8df4e2013c5a'  # 19.5 + 19.8 prediction_value baseline
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("context", sa.Text(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("predictions", "context")
```

---

## Prompt changes

### EXTRACTION_TEMPLATE (`src/prophet_checker/llm/prompts.py`)

Розширюємо output specification:

```python
EXTRACTION_TEMPLATE = """Analyze the following text by {person_name} (published on {published_date}).
Extract all predictions — statements about future events that can later be verified.

Text:
---
{text}
---

For each prediction, extract:
- claim_text: the exact prediction (in original language)
- prediction_date: when the prediction was made (YYYY-MM-DD)
- target_date: when the predicted event should happen (YYYY-MM-DD or null if unclear)
- topic: category (e.g., "війна", "економіка", "політика", "міжнародні відносини")
- context: VERBATIM quote from the post (~300 chars max) that
  shows what the claim refers to. Pick the sentence(s) immediately
  surrounding the claim that explain the situation, persons, or
  preceding events. Must be EXACT text from the post (we validate
  programmatically that this is a substring).

Respond with JSON:
{{"predictions": [{{"claim_text": "...", "prediction_date": "...", "target_date": "...", "topic": "...", "context": "..."}}]}}

If no predictions found, respond: {{"predictions": []}}"""
```

`EXTRACTION_SYSTEM` не змінюється.

### `parse_extraction_response`

Жодних змін — функція повертає `data.get("predictions", [])` як list of dicts. Новий ключ `context` потрапляє автоматично.

### `build_verification_prompt_v2` — renamed parameter

```python
def build_verification_prompt_v2(
    claim: str,
    prediction_date: str,
    target_date: str | None,
    today: str,
    context: str,        # <-- was: post_excerpt
) -> str:
    return VERIFICATION_TEMPLATE_V2.format(
        claim=claim,
        prediction_date=prediction_date,
        target_date=target_date or "not specified",
        today=today,
        post_excerpt=context,  # template placeholder name kept
    )
```

`VERIFICATION_TEMPLATE_V2` залишається без змін — заголовок "Original post excerpt (for context):" семантично коректний і для нового formatu.

---

## Validation logic

Нова утиліта (розташування — `src/prophet_checker/llm/prompts.py`, бо там уже parser + builder):

```python
def validate_context_in_post(context: str, raw_post: str) -> bool:
    if not context or not raw_post:
        return False
    norm_ctx = " ".join(context.split())
    if not norm_ctx:           # whitespace-only context
        return False
    norm_post = " ".join(raw_post.split())
    return norm_ctx in norm_post
```

**Whitespace normalize idiom:** `" ".join(s.split())` колапсує усі whitespace runs до одного пробілу + тримить кінці. Це Pythonic equivalent `re.sub(r"\s+", " ", s).strip()`.

**Що НЕ покриває (acceptable для pet project):**
- Unicode NBSP / em-space — `str.split()` ловить більшість
- Smart quotes vs straight quotes
- Case sensitivity (raw post і LLM output обидва preserve case)

Якщо у 19.8b run побачимо багато drops через punctuation — додамо `unicodedata.normalize('NFKC', ...)` перед split.

**Хто викликає validator:** Task 19.8a НЕ wires validator у production extraction pipeline (production extractor буде wired у 19.8b operational script + Task 20). 19.8a лише надає function + tests. У 19.8b run script виглядатиме:

```python
for claim in parse_extraction_response(response):
    if not validate_context_in_post(claim.get("context", ""), raw_post):
        logger.warning(f"Drop — context not in post: {claim['claim_text'][:60]}")
        stats["context_drops"] += 1
        continue
    ...save
```

---

## Tests delta

| # | Test name | File | Asserts |
|---|---|---|---|
| 1 | `test_prediction_has_context_field_default` | tests/test_models.py | `Prediction(...).context is None` |
| 2 | `test_extraction_template_includes_context_field` | tests/test_llm_prompts.py | `"context: VERBATIM quote"` in EXTRACTION_TEMPLATE |
| 3 | `test_parse_extraction_response_extracts_context` | tests/test_llm_prompts.py | parsed[0]["context"] == expected |
| 4 | `test_validate_context_in_post_success` | tests/test_llm_prompts.py | True для substring match |
| 5 | `test_validate_context_in_post_fails_on_hallucination` | tests/test_llm_prompts.py | False якщо context ∉ post |
| 6 | `test_validate_context_normalizes_whitespace` | tests/test_llm_prompts.py | newlines/tabs у post — все одно match |
| 7 | `test_validate_context_empty_inputs` | tests/test_llm_prompts.py | (empty ctx → False), (empty post → False), (whitespace-only ctx → False) |
| 8 | `test_domain_to_prediction_db_includes_context` | tests/test_storage_postgres.py | Mapper round-trip |
| 9 | `test_prediction_db_to_domain_includes_context` | tests/test_storage_postgres.py | Reverse mapper |
| 10 | `test_prediction_context_migration_loads` | tests/test_alembic.py | Sanity load |
| 11 | `test_build_verification_prompt_v2_accepts_context_kwarg` | tests/test_llm_prompts.py | New `context=` param name works |

**Fixture updates (existing tests):**
- `test_build_verification_prompt_v2_substitutes_all_fields`: змінити `post_excerpt=` на `context=` у виклику

**Test count delta:** +11 нових, ~1 fixture rename. Поточний: 139 → 150.

---

## Out of scope

- ❌ **Re-run extraction** на існуючих посах — Task 19.8b
- ❌ **Re-evaluate extraction quality** (vs gemini-flash-lite V1) — Task 19.8b
- ❌ **Manual context review** для 35 gold — Task 19.8b
- ❌ **Production extractor wiring** (analysis/extractor.py зміни) — Task 20
- ❌ **Migration of legacy predictions** — пет проект, prod даних ще немає
- ❌ **Multi-snippet context** (один context per claim, не масив)
- ❌ **Fuzzy match для validation** — drop hard, переходимо до більш агресивного normalize якщо побачимо drops у 19.8b
- ❌ **Context length enforcement** (труncate до 300 chars) — модель отримує hint у prompt, не примусово trim'имо output
- ❌ **Context language detection** — extractor працює з мовою оригінального посту

---

## File list

**Modify:**
- `src/prophet_checker/models/domain.py` — Prediction.context field
- `src/prophet_checker/models/db.py` — PredictionDB.context column
- `src/prophet_checker/storage/postgres.py` — mapper round-trip
- `src/prophet_checker/llm/prompts.py` — EXTRACTION_TEMPLATE expanded, build_verification_prompt_v2 param rename, new validate_context_in_post function
- `tests/test_models.py` — +1 test
- `tests/test_llm_prompts.py` — +6 tests, 1 fixture rename
- `tests/test_storage_postgres.py` — +2 mapper tests
- `tests/test_alembic.py` — +1 sanity test

**Create:**
- `alembic/versions/<rev>_add_prediction_context.py` — міграція

**Down_revision chain:**
```
edb2e385f26b (initial)
  → 30fd925789cb (V2 metadata)
    → 8df4e2013c5a (prediction_value)
      → <new> (prediction context)
```

---

## Implementation notes

1. **Order of TDD steps** (для писання плану):
   - Domain field + 1 test → commit
   - DB column → commit
   - Mappers + 2 tests → commit
   - Validator function + 4 tests → commit
   - EXTRACTION_TEMPLATE expand + 2 tests → commit
   - build_verification_prompt_v2 param rename + 1 test → commit
   - Alembic migration + 1 sanity test → commit
   - Total: ~7 commits

2. **Backward compatibility:** Pydantic `context: str | None = None` дозволяє створювати predictions без context (наприклад у unit tests, де context не релевантний). DB nullable теж — legacy data не падає.

3. **Pre-existing fixtures:** `tests/test_models.py` уже має `Prediction(...)` фабрику без context — нічого не ламається завдяки nullable default.

---

## Cross-references

- **V2 verification spec:** [`../verifier-v2/2026-04-26-verification-trigger-policy-design.md`](../verifier-v2/2026-04-26-verification-trigger-policy-design.md)
- **Task 19.5 foundations:** [`2026-05-07-task-19-5-schema-prompts-design.md`](2026-05-07-task-19-5-schema-prompts-design.md)
- **Task 19.7a gold dataset:** [`2026-05-12-task-19-7a-gold-labeling-design.md`](2026-05-12-task-19-7a-gold-labeling-design.md)
- **PredictionValue extension:** [`2026-05-12-prediction-value-extension-plan.md`](2026-05-12-prediction-value-extension-plan.md)
- **Task 19.8b** (sibling, brainstorm next): re-run + manual review
