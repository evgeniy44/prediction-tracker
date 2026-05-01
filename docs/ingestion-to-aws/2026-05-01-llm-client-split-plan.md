# LLM Client Split — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split monolithic `LLMClient` (which mixes completion + embedding with single api_key) into two single-responsibility classes — `LLMClient` (completion only) and `EmbeddingClient` (embedding only). Move embed call OUT of `PredictionExtractor`. Remove now-unnecessary `DetectionLLM` wrapper.

**Architecture:** Single Responsibility per class, separate files. Each client owns its own `api_key`. PredictionExtractor returns predictions with `embedding=None`; orchestrator (Task 15) populates embeddings separately.

**Tech Stack:** Python 3.11+, LiteLLM, pytest-asyncio, AsyncMock.

**Spec:** [`2026-05-01-llm-client-split-design.md`](2026-05-01-llm-client-split-design.md)

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `src/prophet_checker/llm/embedding.py` | Create | `EmbeddingClient.embed()` |
| `tests/test_llm_embedding.py` | Create | 3 tests for `EmbeddingClient` |
| `src/prophet_checker/llm/client.py` | Modify | Drop `embed()`, drop `embedding_model` param, drop `aembedding` import |
| `src/prophet_checker/analysis/extractor.py` | Modify | Drop embed call inside `extract()`, return `embedding=None` |
| `tests/test_analysis_extractor.py` | Modify | `make_llm` без embed mock; `assert p.embedding is None`; remove `embed.assert_not_called` line |
| `tests/test_llm_client.py` | Modify | Delete `test_llm_client_embed` |
| `scripts/evaluate_detection.py` | Modify | Delete `DetectionLLM` class, simplify `_default_extractor_factory` |
| `tests/test_evaluate_detection.py` | Modify | Delete 3 `test_detection_llm_*` tests + import |

---

## Task 1: EmbeddingClient (new class + tests)

**Files:**
- Create: `src/prophet_checker/llm/embedding.py`
- Create: `tests/test_llm_embedding.py`

- [ ] **Step 1: Write 3 failing tests**

Create `tests/test_llm_embedding.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from prophet_checker.llm.embedding import EmbeddingClient


@pytest.mark.asyncio
async def test_embedding_client_default_model():
    client = EmbeddingClient(api_key="test-key")
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.1, 0.2, 0.3])]

    with patch("prophet_checker.llm.embedding.aembedding", return_value=mock_response) as mock_call:
        result = await client.embed("Test text")

    assert result == [0.1, 0.2, 0.3]
    call_kwargs = mock_call.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-3-small"
    assert call_kwargs["api_key"] == "test-key"
    assert call_kwargs["input"] == ["Test text"]


@pytest.mark.asyncio
async def test_embedding_client_custom_model():
    client = EmbeddingClient(model="cohere/embed-english-v3.0", api_key="cohere-key")
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.5] * 1024)]

    with patch("prophet_checker.llm.embedding.aembedding", return_value=mock_response) as mock_call:
        await client.embed("Test")

    assert mock_call.call_args.kwargs["model"] == "cohere/embed-english-v3.0"


@pytest.mark.asyncio
async def test_embedding_client_no_api_key_passes_none():
    client = EmbeddingClient()
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.0])]

    with patch("prophet_checker.llm.embedding.aembedding", return_value=mock_response) as mock_call:
        await client.embed("Test")

    assert mock_call.call_args.kwargs["api_key"] is None
```

- [ ] **Step 2: Run tests, verify ImportError**

```bash
.venv/bin/python -m pytest tests/test_llm_embedding.py -v
```

Expected: 3 errors — `ModuleNotFoundError: No module named 'prophet_checker.llm.embedding'`.

- [ ] **Step 3: Create EmbeddingClient**

Create `src/prophet_checker/llm/embedding.py`:

```python
from __future__ import annotations

from litellm import aembedding


class EmbeddingClient:
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        num_retries: int = 3,
    ):
        self._model = model
        self._api_key = api_key
        self._num_retries = num_retries

    async def embed(self, text: str) -> list[float]:
        response = await aembedding(
            model=self._model,
            input=[text],
            api_key=self._api_key,
            num_retries=self._num_retries,
        )
        return response.data[0].embedding
```

- [ ] **Step 4: Run tests, verify all 3 pass**

```bash
.venv/bin/python -m pytest tests/test_llm_embedding.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run full suite, verify no regression**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 102 prior + 3 new = **105 passing**.

- [ ] **Step 6: Commit**

```bash
git add src/prophet_checker/llm/embedding.py tests/test_llm_embedding.py
git commit -m "feat(llm): add EmbeddingClient — single-responsibility embed adapter (LLM split)"
```

---

## Task 2: PredictionExtractor — drop embed call

**Files:**
- Modify: `src/prophet_checker/analysis/extractor.py`
- Modify: `tests/test_analysis_extractor.py`

- [ ] **Step 1: Update test fixtures + assertions**

In `tests/test_analysis_extractor.py`:

**1a. Simplify `make_llm` helper.** Find:

```python
def make_llm(complete_return: str, embed_return: list[float] | None = None):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=complete_return)
    llm.embed = AsyncMock(return_value=embed_return or [0.0] * 1536)
    return llm
```

Replace with:

```python
def make_llm(complete_return: str):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=complete_return)
    return llm
```

**1b. Update embedding assertion (line ~55).** Find:

```python
    assert len(p.embedding) == 1536
```

Replace with:

```python
    assert p.embedding is None
```

**1c. Remove now-meaningless line (line ~71).** Find:

```python
    llm.embed.assert_not_called()
```

Delete that line entirely (no embed mock to assert against).

- [ ] **Step 2: Run tests, expect failures**

```bash
.venv/bin/python -m pytest tests/test_analysis_extractor.py -v
```

Expected: tests fail because `extractor` still calls `await self._llm.embed(...)` but `make_llm()` no longer mocks `embed`. The mock returns a `MagicMock` for unknown attributes which doesn't satisfy `await`.

- [ ] **Step 3: Update extractor to drop embed call**

In `src/prophet_checker/analysis/extractor.py`, modify the `extract()` method body. Find the section that generates embedding + appends Prediction:

```python
            # Generate embedding for semantic search
            try:
                embedding = await self._llm.embed(claim)
            except Exception:
                logger.exception("Embedding call failed for claim: %s", claim[:60])
                embedding = None

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
                    embedding=embedding,
                )
            )
```

Replace with:

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

- [ ] **Step 4: Run extractor tests, verify all pass**

```bash
.venv/bin/python -m pytest tests/test_analysis_extractor.py -v
```

Expected: all extractor tests passing (with new `embedding is None` semantic).

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: 105 passing (no regression — Task 4 will fix DetectionLLM-related tests if they break).

If any tests fail other than `test_evaluate_detection` (DetectionLLM-related), investigate before committing.

- [ ] **Step 6: Commit**

```bash
git add src/prophet_checker/analysis/extractor.py tests/test_analysis_extractor.py
git commit -m "refactor(extractor): drop embed call — orchestrator's concern (LLM split)"
```

---

## Task 3: LLMClient — drop embed method

**Files:**
- Modify: `src/prophet_checker/llm/client.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: Read current `tests/test_llm_client.py` to find embed test**

```bash
grep -n "test_llm_client_embed\|aembedding" tests/test_llm_client.py
```

Identify the test function `test_llm_client_embed` and its lines.

- [ ] **Step 2: Delete `test_llm_client_embed` from test file**

In `tests/test_llm_client.py`, delete the entire `test_llm_client_embed` function block (typically ~10-12 lines including decorator). The function references `client.embed()` and `aembedding` patch, neither of which will exist after Task 3.

- [ ] **Step 3: Run remaining tests in file**

```bash
.venv/bin/python -m pytest tests/test_llm_client.py -v
```

Expected: remaining tests (e.g. `test_llm_client_complete`) still pass.

- [ ] **Step 4: Modify `src/prophet_checker/llm/client.py` — strip embed**

Replace the **entire content** of `src/prophet_checker/llm/client.py` with:

```python
from __future__ import annotations

from litellm import acompletion


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        temperature: float = 0.1,
        num_retries: int = 3,
    ):
        self._model = f"{provider}/{model}" if provider != "openai" else model
        self._api_key = api_key
        self._temperature = temperature
        self._num_retries = num_retries

    async def complete(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await acompletion(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            api_key=self._api_key,
            num_retries=self._num_retries,
        )
        return response.choices[0].message.content
```

Changes from current:
- `from litellm import acompletion, aembedding` → `from litellm import acompletion`
- Removed `embedding_model` constructor param
- Removed `self._embedding_model` field
- Removed `embed()` method
- Removed inline comments (per project preference)

- [ ] **Step 5: Run all LLM-related tests**

```bash
.venv/bin/python -m pytest tests/test_llm_client.py tests/test_llm_embedding.py -v
```

Expected: all passing.

- [ ] **Step 6: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: ~104 passing (3 new embedding − 1 deleted). Some `test_evaluate_detection` tests may still pass — DetectionLLM still exists and references `_inner.complete()` which still works. `test_detection_llm_embed_returns_stub_without_api_call` doesn't actually call inner's embed (returns stub) — so it still passes after Task 3. Task 4 deletes DetectionLLM entirely.

- [ ] **Step 7: Commit**

```bash
git add src/prophet_checker/llm/client.py tests/test_llm_client.py
git commit -m "refactor(llm): drop embed() from LLMClient — moved to EmbeddingClient (LLM split)"
```

---

## Task 4: Remove DetectionLLM wrapper + simplify factory

**Files:**
- Modify: `scripts/evaluate_detection.py`
- Modify: `tests/test_evaluate_detection.py`

- [ ] **Step 1: Find DetectionLLM class + factory in script**

```bash
grep -n "class DetectionLLM\|_default_extractor_factory\|DetectionLLM(" scripts/evaluate_detection.py
```

Note line ranges for:
- `class DetectionLLM:` definition (likely ~25 lines)
- `_default_extractor_factory` function

- [ ] **Step 2: Delete `DetectionLLM` class**

In `scripts/evaluate_detection.py`, delete the entire `class DetectionLLM:` block — class definition, all its methods, and any docstring. Roughly 25 lines.

- [ ] **Step 3: Simplify `_default_extractor_factory`**

Find the current factory:

```python
def _default_extractor_factory(model_id: str) -> PredictionExtractor:
    """Build a PredictionExtractor for the given model_id using env-var API keys."""
    if "/" not in model_id:
        raise ValueError(
            f"model_id must be 'provider/model', got {model_id!r}"
        )
    provider, model = model_id.split("/", 1)
    if provider not in PROVIDER_API_KEY_ENV:
        raise ValueError(f"Unknown provider for extraction: {provider!r}")
    api_key = os.environ.get(PROVIDER_API_KEY_ENV[provider])
    if not api_key:
        raise RuntimeError(
            f"Missing API key for provider {provider!r}: "
            f"set env var {PROVIDER_API_KEY_ENV[provider]}"
        )
    client = LLMClient(
        provider=provider, model=model, api_key=api_key, temperature=0.0
    )
    wrapped = DetectionLLM(client)
    return PredictionExtractor(wrapped)
```

Replace `wrapped = DetectionLLM(client)` and `return PredictionExtractor(wrapped)` with a single line:

```python
    return PredictionExtractor(client)
```

(The rest of the factory body — model_id parsing, api_key lookup, LLMClient construction — stays unchanged.)

- [ ] **Step 4: Update `tests/test_evaluate_detection.py` — delete DetectionLLM tests**

Three test functions reference `DetectionLLM`:
1. `test_detection_llm_delegates_complete_to_inner_client`
2. `test_detection_llm_embed_returns_stub_without_api_call`
3. `test_detection_llm_complete_propagates_exceptions`

Delete all three function blocks (typically Group C section, ~50-70 lines total).

Also remove the `DetectionLLM` import. Find the import line near the top:

```python
from evaluate_detection import (
    ...
    DetectionLLM,
    ...
)
```

Delete `DetectionLLM,` from that import list.

If the file's docstring mentions DetectionLLM in test groups summary (e.g. `C — DetectionLLM:      wrapper for multi-provider eval (3 tests)`), update or delete that line.

- [ ] **Step 5: Run evaluate_detection tests, verify all pass**

```bash
.venv/bin/python -m pytest tests/test_evaluate_detection.py -v
```

Expected: tests pass (3 fewer total — 3 DetectionLLM tests deleted).

- [ ] **Step 6: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: **103 passing** (102 baseline − 2 net = 100, plus 3 new EmbeddingClient + 0 DetectionLLM + 0 LLMClient embed = 103).

Sanity calc: 102 baseline + 3 new EmbeddingClient − 1 LLMClient embed test − 3 DetectionLLM tests = **101 passing**. Adjust if numbers slightly differ; key check is full suite passes.

- [ ] **Step 7: Verify no `DetectionLLM` references remain**

```bash
grep -rn "DetectionLLM" --include="*.py" . 2>/dev/null | grep -v __pycache__ | grep -v .venv
```

Expected: empty output (no remaining references in `src/`, `scripts/`, or `tests/`).

If references remain in `docs/` (historical mentions in plan/spec) — those are OK, leave them.

- [ ] **Step 8: Commit**

```bash
git add scripts/evaluate_detection.py tests/test_evaluate_detection.py
git commit -m "refactor(scripts): remove DetectionLLM wrapper — extractor no longer embeds (LLM split)"
```

---

## Final verification

- [ ] **Run full test suite — confirm all passing:**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: ~101-103 tests passing. Specifically:
- Started at 102 (after Task 21 closeout)
- +3 from `test_llm_embedding.py` (Task 1)
- −1 from `test_llm_client.py::test_llm_client_embed` (Task 3)
- −3 from `test_evaluate_detection.py::test_detection_llm_*` (Task 4)
- Net: **101 passing**

- [ ] **Verify file structure:**

```bash
find src/prophet_checker/llm tests -name "test_llm*.py" -o -name "*.py" | grep -E "(llm/|test_llm)"
```

Expected output:
```
src/prophet_checker/llm/__init__.py
src/prophet_checker/llm/client.py
src/prophet_checker/llm/embedding.py
src/prophet_checker/llm/prompts.py
tests/test_llm_client.py
tests/test_llm_embedding.py
tests/test_llm_prompts.py
```

- [ ] **Verify imports work:**

```bash
.venv/bin/python -c "
from prophet_checker.llm.client import LLMClient
from prophet_checker.llm.embedding import EmbeddingClient
print('OK:', LLMClient, EmbeddingClient)
"
```

Expected: `OK: <class 'prophet_checker.llm.client.LLMClient'> <class 'prophet_checker.llm.embedding.EmbeddingClient'>`.

- [ ] **Verify LLMClient no longer has embed:**

```bash
.venv/bin/python -c "
from prophet_checker.llm.client import LLMClient
import inspect
methods = [name for name, _ in inspect.getmembers(LLMClient, predicate=inspect.isfunction)]
print('LLMClient methods:', methods)
assert 'embed' not in methods, 'embed should have been removed!'
"
```

Expected: `LLMClient methods: ['__init__', 'complete']` (and `embed` not in list).

- [ ] **Verify DetectionLLM is gone:**

```bash
grep -rn "DetectionLLM" --include="*.py" . 2>/dev/null | grep -v __pycache__ | grep -v .venv
```

Expected: empty.

---

## Out of scope (explicitly deferred)

- ❌ **Verifier modifications** — `PredictionVerifier` uses `LLMClient.complete()` only; no embed dependency, no signature change.
- ❌ **Real production validation** — Task 19 integration smoke (requires real OpenAI API + pgvector).
- ❌ **Batch embedding** — `EmbeddingClient.embed_batch(texts)` is YAGNI for MVP.
- ❌ **EmbeddingProvider Protocol** — for future Cohere/Voyage/local swappable providers; YAGNI now.
- ❌ **IngestionOrchestrator integration** — Task 15. This refactor is a prerequisite; orchestrator will use both `LLMClient` and `EmbeddingClient` independently.

---

## Cross-references

- Spec: [`2026-05-01-llm-client-split-design.md`](2026-05-01-llm-client-split-design.md)
- IngestionOrchestrator (consumer): [`../architecture/2026-04-26-flow-production-ingestion.md`](../architecture/2026-04-26-flow-production-ingestion.md)
- Master plan: [`../plan/2026-04-08-prophet-checker-plan.md`](../plan/2026-04-08-prophet-checker-plan.md)
