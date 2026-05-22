# Task 19.8c — Wire context into PredictionExtractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `context` field з parsed extraction dict у `PredictionExtractor.extract()`, validate substring проти raw post, drop весь prediction на invalid/missing context. Усуває 19.8a gap і дублювання валідації у 19.8b.

**Architecture:** Один code change у `extractor.py` (import validator + drop loop + context field). Existing fixture оновлюється (V2 response з context). 2 нових drop-тести. Окремий doc commit revise'ить 19.8b plan (remove extractor bypass). Return type `list[Prediction]` незмінний — backward compat.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, asyncio. Working dir: `/Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker`. Use `.venv/bin/python`. Ukrainian commit messages.

**Spec:** [`2026-05-14-task-19-8c-extractor-context-wiring-design.md`](2026-05-14-task-19-8c-extractor-context-wiring-design.md)

**Baseline:** 150 tests pass. Target: 152 (+2 new, 1 fixture update, +1 assertion).

---

## File Structure

| File | Change |
|---|---|
| `src/prophet_checker/analysis/extractor.py` | Import validate_context_in_post; у loop drop on invalid context; додати `context=context` у Prediction(...). |
| `tests/test_analysis_extractor.py` | `LLM_RESPONSE_ONE` +context; `test_extract_returns_predictions` +assertion; +2 drop tests. |
| `docs/verification-track/2026-05-14-task-19-8b-v2-extraction-rerun-plan.md` | Stage 1 revision — remove bypass, use extractor. |

---

## Task 1: Wire context into extractor (TDD)

**Files:**
- Modify: `src/prophet_checker/analysis/extractor.py`
- Modify: `tests/test_analysis_extractor.py`

### Step 1: Оновити `LLM_RESPONSE_ONE` fixture

У `tests/test_analysis_extractor.py`, знайти `LLM_RESPONSE_ONE` і замінити на:

```python
LLM_RESPONSE_ONE = json.dumps({
    "predictions": [
        {
            "claim_text": "Контрнаступ почнеться влітку 2023 року",
            "prediction_date": "2023-01-15",
            "target_date": "2023-06-01",
            "topic": "війна",
            "context": "Контрнаступ почнеться влітку 2023 року",
        }
    ]
})
```

### Step 2: Додати assertion у `test_extract_returns_predictions`

У тому ж файлі, у `test_extract_returns_predictions`, ПІСЛЯ рядка `assert p.topic == "війна"`, додати:

```python
    assert p.context == "Контрнаступ почнеться влітку 2023 року"
```

### Step 3: Додати 2 нових drop-тести

Append до `tests/test_analysis_extractor.py`:

```python
async def test_extract_drops_prediction_with_hallucinated_context():
    response = json.dumps({"predictions": [{
        "claim_text": "Війна закінчиться скоро",
        "prediction_date": "2023-01-15", "target_date": None, "topic": "війна",
        "context": "цього тексту немає в оригінальному пості взагалі",
    }]})
    llm = make_llm(response)
    extractor = PredictionExtractor(llm)
    predictions = await extractor.extract(
        text="Реальний пост: Війна закінчиться скоро, я впевнений.",
        person_id="p1", document_id="d1", person_name="Арестович",
        published_date="2023-01-15",
    )
    assert predictions == []


async def test_extract_drops_prediction_with_missing_context():
    response = json.dumps({"predictions": [{
        "claim_text": "Щось станеться",
        "prediction_date": "2023-01-15", "target_date": None, "topic": "війна",
    }]})
    llm = make_llm(response)
    extractor = PredictionExtractor(llm)
    predictions = await extractor.extract(
        text="Реальний пост без потрібного context.",
        person_id="p1", document_id="d1", person_name="Арестович",
        published_date="2023-01-15",
    )
    assert predictions == []
```

### Step 4: Запустити тести — verify failures

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_analysis_extractor.py -v
```

Expected:
- `test_extract_returns_predictions` FAIL (`p.context` is None, але fixture тепер має context — насправді fail бо extractor ще не мапить context → `assert p.context == "..."` отримує None)
- `test_extract_drops_prediction_with_hallucinated_context` FAIL (extractor ще не drop'ить — повертає 1 prediction замість [])
- `test_extract_drops_prediction_with_missing_context` FAIL (те саме)
- `test_extract_no_predictions`, `test_extract_llm_error_returns_empty` PASS (не зачіпаються)

### Step 5: Оновити import у extractor.py

У `src/prophet_checker/analysis/extractor.py`, знайти import block:

```python
from prophet_checker.llm.prompts import (
    build_extraction_prompt,
    get_extraction_system,
    parse_extraction_response,
)
```

Замінити на:

```python
from prophet_checker.llm.prompts import (
    build_extraction_prompt,
    get_extraction_system,
    parse_extraction_response,
    validate_context_in_post,
)
```

### Step 6: Додати validation drop + context field у loop

У `src/prophet_checker/analysis/extractor.py`, у `extract()` методі, знайти block:

```python
        for raw in raw_predictions:
            claim = raw.get("claim_text", "").strip()
            if not claim:
                continue

            # Parse optional target_date
```

Вставити validation drop МІЖ `if not claim: continue` і коментарем `# Parse optional target_date`:

```python
        for raw in raw_predictions:
            claim = raw.get("claim_text", "").strip()
            if not claim:
                continue

            context = raw.get("context")
            if not validate_context_in_post(context, text):
                logger.warning(
                    "Drop prediction — invalid/missing context: %r", claim[:60]
                )
                continue

            # Parse optional target_date
```

Потім знайти `Prediction(...)` construction:

```python
            predictions.append(
                Prediction(
                    id=str(uuid4()),
                    person_id=person_id,
                    document_id=document_id,
                    claim_text=claim,
                    prediction_date=prediction_date,
                    target_date=target_date,
                    topic=raw.get("topic", ""),
                    status=PredictionStatus.UNRESOLVED,
                    confidence=0.0,
                    evidence_url=None,
                    evidence_text=None,
                    embedding=None,
                )
            )
```

Додати `context=context,` ПІСЛЯ `claim_text=claim,`:

```python
            predictions.append(
                Prediction(
                    id=str(uuid4()),
                    person_id=person_id,
                    document_id=document_id,
                    claim_text=claim,
                    context=context,
                    prediction_date=prediction_date,
                    target_date=target_date,
                    topic=raw.get("topic", ""),
                    status=PredictionStatus.UNRESOLVED,
                    confidence=0.0,
                    evidence_url=None,
                    evidence_text=None,
                    embedding=None,
                )
            )
```

### Step 7: Запустити тести — verify pass

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_analysis_extractor.py -v
```

Expected: усі 5 тестів PASS (3 existing + 2 нових).

### Step 8: Full suite check

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest 2>&1 | tail -3
```

Expected: `152 passed`

### Step 9: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git add src/prophet_checker/analysis/extractor.py tests/test_analysis_extractor.py && git commit -m "feat(analysis): extractor wire context + drop on invalid context"
```

---

## Task 2: Revise 19.8b plan doc

**Files:**
- Modify: `docs/verification-track/2026-05-14-task-19-8b-v2-extraction-rerun-plan.md`

Doc-only change. 19.8b Stage 1 (`v2_extraction_run.py`) більше не bypass'ить extractor.

### Step 1: Прочитати поточний 19.8b plan Task 1 section

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && sed -n '/## Task 1: Create/,/## Task 2: Execute/p' docs/verification-track/2026-05-14-task-19-8b-v2-extraction-rerun-plan.md | head -200
```

Зрозуміти поточну структуру Task 1 (містить `extract_v2`, `validate_and_drop`, тести).

### Step 2: Замінити Task 1 "Approach" + skeleton

У `docs/verification-track/2026-05-14-task-19-8b-v2-extraction-rerun-plan.md`, знайти секцію Task 1 ("### Approach: bypass PredictionExtractor") і замінити на нову версію що використовує extractor.

Замінити блок `### Approach: bypass PredictionExtractor` (включно з поясненням) на:

```markdown
### Approach: use PredictionExtractor (post-19.8c)

Task 19.8c wired context + validation у `PredictionExtractor.extract()`. Тому
`v2_extraction_run.py` використовує extractor напряму — без bypass, без дублювання
validate logic. Extractor повертає `list[Prediction]` (вже validated, context populated,
hallucinated-context claims dropped). Script тільки serializes їх у JSON.
```

### Step 3: Замінити v2_extraction_run.py skeleton у плані

У Task 1 Step 1 code block, замінити функції `build_llm_client`, `extract_v2`, `validate_and_drop`, `run_extraction` на версію що використовує extractor:

```python
from evaluate_detection import (
    PROVIDER_API_KEY_ENV,
    MIN_CALL_INTERVAL_SECONDS,
)
from prophet_checker.analysis.extractor import PredictionExtractor
from prophet_checker.llm.client import LLMClient

# ... select_posts_for_v2 unchanged ...

def build_extractor(model_id: str) -> PredictionExtractor:
    if "/" not in model_id:
        raise ValueError(f"model_id must be 'provider/model', got {model_id!r}")
    provider, model = model_id.split("/", 1)
    env_var = PROVIDER_API_KEY_ENV.get(provider)
    if not env_var:
        raise ValueError(f"Unknown provider {provider!r}")
    api_key = os.environ.get(env_var)
    if not api_key:
        raise RuntimeError(f"Missing API key for {provider!r}: set {env_var}")
    client = LLMClient(provider=provider, model=model, api_key=api_key, temperature=0.0)
    return PredictionExtractor(client)


def serialize_v2_prediction(p) -> dict:
    return {
        "claim_text": p.claim_text,
        "context": p.context,
        "prediction_date": p.prediction_date.isoformat() if p.prediction_date else None,
        "target_date": p.target_date.isoformat() if p.target_date else None,
        "topic": p.topic,
    }


async def run_extraction(model_id: str, posts: list[dict], min_interval: float) -> tuple[list[dict], dict]:
    extractor = build_extractor(model_id)
    extractions: list[dict] = []
    total_kept = 0

    for post in posts:
        preds = await extractor.extract(
            text=post["text"],
            person_id=post["person_name"],
            document_id=post["id"],
            person_name=post["person_name"],
            published_date=post["published_at"],
        )
        claims = [serialize_v2_prediction(p) for p in preds]
        total_kept += len(claims)
        extractions.append({
            "post_id": post["id"],
            "post_published_at": post["published_at"],
            "post_text": post["text"],
            "claims": claims,
        })
        if min_interval > 0:
            await asyncio.sleep(min_interval)

    stats = {
        "posts_processed": len(posts),
        "claims_kept": total_kept,
    }
    return extractions, stats
```

Note у плані: import `validate_context_in_post` та функції `extract_v2`/`validate_and_drop` ВИДАЛЕНО (валідація тепер в extractor). `claims_raw` і `claims_hallucinated_drop` stats прибрано (extractor логує drops через warning, не повертає count). Metadata тепер `{posts_processed, claims_kept}`.

### Step 4: Прибрати validate_and_drop тести з 19.8b plan Task 1 Step 2

У 19.8b plan, Task 1 Step 2 (`tests/test_v2_extraction_run.py`), видалити тести `test_validate_and_drop_keeps_valid_claims` і `test_validate_and_drop_handles_empty_context`. Залишити тільки `test_select_posts_for_v2_keeps_only_posts_with_v1_claims` і `test_select_posts_for_v2_filters_by_author`.

Оновити expected test counts у 19.8b plan:
- Task 1 Step 4: `152 passed` (150 baseline + 2 select_posts tests) — але це після 19.8c landed (152 baseline), тож `154 passed`
- Final verification: `154 passed`

Замінити всі згадки "154 passed (150 baseline + 4 new)" → "154 passed (152 post-19.8c baseline + 2 select_posts tests)".

### Step 5: Додати prerequisite note у 19.8b plan header

У 19.8b plan, після рядка `**Prerequisites:** ✅ Task 19.8a landed...`, додати:

```markdown
**Prerequisites (updated):** ✅ Task 19.8a + ✅ Task 19.8c (extractor context wiring). `PredictionExtractor.extract()` тепер повертає Prediction objects з validated context — Stage 1 використовує extractor напряму.
```

### Step 6: Commit

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git add docs/verification-track/2026-05-14-task-19-8b-v2-extraction-rerun-plan.md && git commit -m "docs: revise 19.8b plan — Stage 1 використовує extractor (post-19.8c)"
```

---

## Task 3: Final verification

**Files:** none (verification only)

### Step 1: Full suite

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest 2>&1 | tail -3
```

Expected: `152 passed`

### Step 2: Git log — 2 нових commits

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git log --oneline | head -5
```

Expected (most recent 2):
- `<hash>` docs: revise 19.8b plan — Stage 1 використовує extractor (post-19.8c)
- `<hash>` feat(analysis): extractor wire context + drop on invalid context

### Step 3: Manual smoke — extractor drops hallucinated context

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import asyncio, json
from unittest.mock import AsyncMock, MagicMock
from prophet_checker.analysis.extractor import PredictionExtractor

def make_llm(resp):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=resp)
    return llm

async def main():
    # Valid context — kept
    valid = json.dumps({'predictions': [{
        'claim_text': 'X станеться', 'prediction_date': '2024-01-01',
        'target_date': None, 'topic': 'політика',
        'context': 'що X станеться невдовзі',
    }]})
    ex = PredictionExtractor(make_llm(valid))
    preds = await ex.extract(text='Я думаю що X станеться невдовзі, точно.',
        person_id='p', document_id='d', person_name='A', published_date='2024-01-01')
    print('Valid context kept:', len(preds) == 1, '| context:', preds[0].context if preds else None)

    # Hallucinated context — dropped
    bad = json.dumps({'predictions': [{
        'claim_text': 'Y станеться', 'prediction_date': '2024-01-01',
        'target_date': None, 'topic': 'політика',
        'context': 'текст якого немає у пості',
    }]})
    ex2 = PredictionExtractor(make_llm(bad))
    preds2 = await ex2.extract(text='Реальний пост про щось інше.',
        person_id='p', document_id='d', person_name='A', published_date='2024-01-01')
    print('Hallucinated context dropped:', preds2 == [])

asyncio.run(main())
"
```

Expected:
```
Valid context kept: True | context: що X станеться невдовзі
Hallucinated context dropped: True
```

### Step 4: Smoke — backward compat (existing callers import OK)

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from prophet_checker.analysis.extractor import PredictionExtractor
import inspect
sig = inspect.signature(PredictionExtractor.extract)
print('extract() params:', list(sig.parameters.keys()))
print('Return annotation:', sig.return_annotation)
"
```

Expected: params include `self, text, person_id, document_id, person_name, published_date`; return annotation `list[Prediction]` (unchanged).

---

## Done criteria

- ✅ 152 tests pass
- ✅ 2 нових commits (feat(analysis) + docs)
- ✅ Extractor drops hallucinated/missing context, populates valid context
- ✅ Return type `list[Prediction]` unchanged (backward compat)
- ✅ 19.8b plan doc revised — Stage 1 uses extractor, no bypass

---

## Caveats для implementer

1. **Task 1 Step 4 expected failures:** після оновлення fixture (context added) АЛЕ перед extractor change, `test_extract_returns_predictions` fails бо extractor ще не мапить context (p.context is None != fixture's context). Це коректний red state — extractor change (Steps 5-6) робить green.

2. **validate_context_in_post вже landed (19.8a).** Не реімплементувати — тільки import.

3. **Task 2 — doc-only.** Implementer редагує markdown plan файл, НЕ створює v2_extraction_run.py (це робота 19.8b execution пізніше). Мета — щоб 19.8b plan відображав post-19.8c reality.

4. **Backward compat:** evaluate_detection.py + extraction_quality_eval.py callers НЕ змінюються (return type stays list[Prediction]). Їх НЕ чіпати у цьому таску.
