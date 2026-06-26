# Eval Pipeline (`eval_common`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Збудувати спільний узагальнений eval-каркас `scripts/eval_common/` (dataset→runner→scorer→reporter), на якому далі пишеться generation-eval і ретрофітяться наявні.

**Architecture:** Узагальнені Pydantic-типи (`EvalCase`/`EvalRun`/`ScoreCard`/`ScoredRun`/`EvalReport`) + конкурентний `run_cases` (ізоляція помилок) + `Scorer`/`Judge` Protocol-и з judge-гігієною + `write_report` (JSON+MD) + тонкий `run_eval()`. Консумер приносить свої `input`/`labels`/`Metrics`-сабтайпи, скорери й aggregate. Переюзає прод-`LLMClient`; нічого не форкає.

**Tech Stack:** Python 3.14, Pydantic v2 (`SerializeAsAny`), LiteLLM (`LLMClient`), pytest (`asyncio_mode=auto`), ruff.

**Design:** [`2026-06-25-eval-pipeline-design.md`](2026-06-25-eval-pipeline-design.md)

---

## Plan-level уточнення дизайну (важливо)

1. **`SerializeAsAny[BaseModel]` для всіх поліморфних полів** (`input`, `labels`, `result`, `detail`, `metrics`).
   Pydantic v2 при серіалізації поля, типізованого базовим класом, відкидає поля сабкласу — `SerializeAsAny`
   змушує серіалізувати рантайм-тип. Без цього `report.json` губив би `input.question` тощо.
2. **`EvalReport` неузагальнений** (`metrics: SerializeAsAny[BaseModel]`), а не `EvalReport[M]`.
   Та сама причина + уникнення Pydantic generic-instantiation пастки. Консумер звужує тип у місці
   використання (як для `input`/`result`). Це уточнює відкрите питання дизайну про `M`.
3. **Throttle-таблиці НЕ переносимо** в цьому циклі (це частина ретрофіту наявних евалів). `run_cases`
   бере `concurrency`/`min_interval_s` параметрами; консумер передає значення. `clients.py` дає лише
   `build_eval_llm` + `parse_model_id`.

---

## File Structure

```
scripts/eval_common/
  __init__.py        # run_eval() + ре-експорт публічних імен        [Task 7]
  models.py          # EvalCase, EvalRun, ScoreCard, ScoredRun, EvalMetadata, EvalReport  [Task 1]
  clients.py         # build_eval_llm(), parse_model_id(), PROVIDER_API_KEY_ENV          [Task 2]
  judge.py           # Judge Protocol, LLMJudge, fingerprint_prompt(), shuffle_options() [Task 3]
  protocols.py       # Scorer Protocol                                                    [Task 4]
  fakes.py           # FakeJudge, fake_sut()                                              [Task 4]
  runner.py          # run_cases()                                                        [Task 5]
  report.py          # write_report(), _render_md()                                       [Task 6]
tests/
  test_eval_common_clients.py     [Task 2]
  test_eval_common_judge.py       [Task 3]
  test_eval_common_runner.py      [Task 5]
  test_eval_common_report.py      [Task 6]
  test_eval_common_run_eval.py    [Task 7]
```

Конвенції: пакет під `scripts/` → імпорт як `eval_common.X` (pythonpath має `scripts`). Тести async без
маркера (`asyncio_mode=auto`). Коміти — укр. conventional. Чисті Pydantic-моделі **не** unit-тестуємо
(CLAUDE.md) — їх покривають тести компонентів, що їх серіалізують/споживають.

---

### Task 1: Пакет + доменні типи `models.py`

**Files:**
- Create: `scripts/eval_common/__init__.py` (порожній на цьому кроці — наповнимо в Task 7)
- Create: `scripts/eval_common/models.py`

Чисті Pydantic-моделі (лише поля) — unit-тесту немає (CLAUDE.md); поведінку `SerializeAsAny`
перевіряє Task 6 (report).

- [ ] **Step 1: Створити порожній пакетний init**

```python
# scripts/eval_common/__init__.py
```
(порожній файл — щоб `eval_common` став пакетом; `run_eval` додамо в Task 7)

- [ ] **Step 2: Написати `models.py`**

```python
# scripts/eval_common/models.py
from __future__ import annotations

from pydantic import BaseModel, SerializeAsAny


class EvalCase(BaseModel):
    id: str
    # SerializeAsAny: зберегти поля сабкласу при дампі в JSON (узагальнена база, типізований сабтайп)
    input: SerializeAsAny[BaseModel]
    labels: SerializeAsAny[BaseModel] | None = None


class EvalRun(BaseModel):
    case: EvalCase
    result: SerializeAsAny[BaseModel] | None = None  # вихід SUT; None якщо SUT впав
    latency_s: float
    error: str | None = None  # тип винятку, не повідомлення/payload


class ScoreCard(BaseModel):
    scorer: str
    score: float | None  # None = не застосовано (SUT впав / нерелевантно)
    detail: SerializeAsAny[BaseModel] | None = None


class ScoredRun(BaseModel):
    run: EvalRun
    cards: list[ScoreCard]


class EvalMetadata(BaseModel):
    eval_name: str
    created_at: str  # UTC ISO, ставить консумер
    n_cases: int
    sut_models: dict[str, str] = {}
    judge_id: str | None = None
    prompt_fingerprints: dict[str, str] = {}
    dataset_path: str | None = None  # None якщо інлайн/синтез


class EvalReport(BaseModel):
    metadata: EvalMetadata
    metrics: SerializeAsAny[BaseModel]  # Metrics-сабтайп консумера
    runs: list[ScoredRun]
```

- [ ] **Step 3: Перевірити імпорт**

Run: `.venv/bin/python -c "import eval_common.models as m; print(m.EvalCase, m.EvalReport)"`
Expected: друкує класи без помилок.

- [ ] **Step 4: Lint + commit**

```bash
.venv/bin/ruff check scripts/eval_common/ && .venv/bin/ruff format scripts/eval_common/
git add scripts/eval_common/__init__.py scripts/eval_common/models.py
git commit -m "feat(eval-common): доменні типи пайплайна (EvalCase/Run/ScoreCard/Report)"
```

---

### Task 2: `clients.py` — `build_eval_llm`

**Files:**
- Create: `scripts/eval_common/clients.py`
- Test: `tests/test_eval_common_clients.py`

- [ ] **Step 1: Написати падаючі тести**

```python
# tests/test_eval_common_clients.py
import pytest

from eval_common.clients import build_eval_llm, parse_model_id
from prophet_checker.llm.client import LLMClient


def test_parse_model_id_valid():
    assert parse_model_id("gemini/gemini-3.1-flash-lite-preview") == (
        "gemini",
        "gemini-3.1-flash-lite-preview",
    )


def test_parse_model_id_rejects_bare():
    with pytest.raises(ValueError):
        parse_model_id("gpt-5-mini")


def test_build_eval_llm_unknown_provider():
    with pytest.raises(ValueError):
        build_eval_llm("foo/bar")


def test_build_eval_llm_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        build_eval_llm("gemini/gemini-3.1-flash-lite-preview")


def test_build_eval_llm_happy(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    llm = build_eval_llm("gemini/gemini-3.1-flash-lite-preview")
    assert isinstance(llm, LLMClient)
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_eval_common_clients.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval_common.clients'`

- [ ] **Step 3: Написати `clients.py`**

```python
# scripts/eval_common/clients.py
from __future__ import annotations

import os

from prophet_checker.llm.client import LLMClient

PROVIDER_API_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "groq": "GROQ_API_KEY",
}


def parse_model_id(model_id: str) -> tuple[str, str]:
    if "/" not in model_id:
        raise ValueError(f"model_id must be 'provider/model', got {model_id!r}")
    provider, model = model_id.split("/", 1)
    return provider, model


def build_eval_llm(model_id: str, *, temperature: float | None = 0.0) -> LLMClient:
    """Build an LLMClient from 'provider/model' using env-var API keys (temp=0 for evals)."""
    provider, model = parse_model_id(model_id)
    if provider not in PROVIDER_API_KEY_ENV:
        raise ValueError(
            f"Unknown provider {provider!r}. Supported: {list(PROVIDER_API_KEY_ENV)}"
        )
    env_var = PROVIDER_API_KEY_ENV[provider]
    api_key = os.environ.get(env_var)
    if not api_key:
        raise RuntimeError(f"Missing API key for {provider!r}: set env var {env_var}")
    return LLMClient(provider=provider, model=model, api_key=api_key, temperature=temperature)
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_eval_common_clients.py -q`
Expected: PASS (5 тестів)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check scripts/eval_common/clients.py tests/test_eval_common_clients.py
.venv/bin/ruff format scripts/eval_common/clients.py tests/test_eval_common_clients.py
git add scripts/eval_common/clients.py tests/test_eval_common_clients.py
git commit -m "feat(eval-common): build_eval_llm + parse_model_id"
```

---

### Task 3: `judge.py` — Judge Protocol + LLMJudge + гігієна

**Files:**
- Create: `scripts/eval_common/judge.py`
- Test: `tests/test_eval_common_judge.py`

Тестуємо **чисті helper-и** (`fingerprint_prompt`, `shuffle_options`). `LLMJudge` — тонка обгортка
над `LLMClient`, мережу не тестуємо (покривається фейком у консумера).

- [ ] **Step 1: Написати падаючі тести**

```python
# tests/test_eval_common_judge.py
from eval_common.judge import fingerprint_prompt, shuffle_options


def test_fingerprint_prompt_deterministic_and_known():
    assert fingerprint_prompt("abc") == fingerprint_prompt("abc")
    assert fingerprint_prompt("abc") != fingerprint_prompt("abd")
    # sha256("abc") = ba7816bf...
    assert fingerprint_prompt("abc").startswith("ba7816bf")


def test_shuffle_options_deterministic_complete_nonmutating():
    opts = ["a", "b", "c", "d", "e"]
    s1 = shuffle_options(opts, seed=42)
    s2 = shuffle_options(opts, seed=42)
    assert s1 == s2  # детерміновано за seed
    assert sorted(s1) == sorted(opts)  # усі опції присутні
    assert opts == ["a", "b", "c", "d", "e"]  # вхід не мутовано
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_eval_common_judge.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval_common.judge'`

- [ ] **Step 3: Написати `judge.py`**

```python
# scripts/eval_common/judge.py
from __future__ import annotations

import hashlib
import random
from typing import Protocol

from prophet_checker.llm.client import LLMClient


class Judge(Protocol):
    id: str

    async def assess(self, prompt: str, *, system: str) -> str: ...


class LLMJudge:
    """Real judge: LLMClient (build with temperature=0). Returns raw text; eval parses it."""

    def __init__(self, llm: LLMClient, judge_id: str) -> None:
        self._llm = llm
        self.id = judge_id

    async def assess(self, prompt: str, *, system: str) -> str:
        return await self._llm.complete(prompt, system=system)


def fingerprint_prompt(text: str) -> str:
    """Stable sha256 of a prompt — pin into EvalMetadata so 'judge said X' is reproducible."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shuffle_options(options: list[str], seed: int) -> list[str]:
    """Deterministic permutation of rubric options (mitigates model-specific position bias)."""
    rng = random.Random(seed)
    shuffled = list(options)
    rng.shuffle(shuffled)
    return shuffled
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_eval_common_judge.py -q`
Expected: PASS (2 тести)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check scripts/eval_common/judge.py tests/test_eval_common_judge.py
.venv/bin/ruff format scripts/eval_common/judge.py tests/test_eval_common_judge.py
git add scripts/eval_common/judge.py tests/test_eval_common_judge.py
git commit -m "feat(eval-common): Judge Protocol + LLMJudge + fingerprint/shuffle гігієна"
```

---

### Task 4: `protocols.py` (Scorer) + `fakes.py`

**Files:**
- Create: `scripts/eval_common/protocols.py`
- Create: `scripts/eval_common/fakes.py`

Інтерфейс + тест-дублі — окремого unit-тесту немає (покриваються Task 5/7).

- [ ] **Step 1: Написати `protocols.py`**

```python
# scripts/eval_common/protocols.py
from __future__ import annotations

from typing import Protocol

from eval_common.models import EvalRun, ScoreCard


class Scorer(Protocol):
    name: str

    async def score(self, run: EvalRun) -> ScoreCard: ...
```

- [ ] **Step 2: Написати `fakes.py`**

```python
# scripts/eval_common/fakes.py
from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from eval_common.models import EvalCase


class FakeJudge:
    """Deterministic judge for tests — returns a canned response, ignores the prompt."""

    id = "fake-judge"

    def __init__(self, response: str = "{}") -> None:
        self._response = response

    async def assess(self, prompt: str, *, system: str) -> str:
        return self._response


def fake_sut(result: BaseModel) -> Callable[[EvalCase], Awaitable[BaseModel]]:
    """Return a run_one callable that yields a fixed result regardless of the case."""

    async def _run_one(case: EvalCase) -> BaseModel:
        return result

    return _run_one
```

- [ ] **Step 3: Перевірити імпорт**

Run: `.venv/bin/python -c "from eval_common.protocols import Scorer; from eval_common.fakes import FakeJudge, fake_sut; print('ok')"`
Expected: друкує `ok`.

- [ ] **Step 4: Lint + commit**

```bash
.venv/bin/ruff check scripts/eval_common/protocols.py scripts/eval_common/fakes.py
.venv/bin/ruff format scripts/eval_common/protocols.py scripts/eval_common/fakes.py
git add scripts/eval_common/protocols.py scripts/eval_common/fakes.py
git commit -m "feat(eval-common): Scorer Protocol + фейки (FakeJudge, fake_sut)"
```

---

### Task 5: `runner.py` — `run_cases`

**Files:**
- Create: `scripts/eval_common/runner.py`
- Test: `tests/test_eval_common_runner.py`

- [ ] **Step 1: Написати падаючі тести**

```python
# tests/test_eval_common_runner.py
from pydantic import BaseModel

from eval_common.models import EvalCase
from eval_common.runner import run_cases


class _In(BaseModel):
    n: int


class _Out(BaseModel):
    n: int


async def test_run_cases_isolates_errors_and_captures_latency():
    cases = [EvalCase(id=str(i), input=_In(n=i)) for i in range(3)]

    async def run_one(case):
        if case.id == "1":
            raise RuntimeError("boom")
        return _Out(n=case.input.n)

    runs = await run_cases(cases, run_one, concurrency=2)
    by_id = {r.case.id: r for r in runs}

    assert len(runs) == 3
    assert by_id["1"].result is None
    assert by_id["1"].error == "RuntimeError"  # тип, не повідомлення
    assert by_id["0"].result is not None
    assert by_id["0"].error is None
    assert all(r.latency_s >= 0.0 for r in runs)


async def test_run_cases_empty_returns_empty():
    async def run_one(case):
        return _Out(n=0)

    assert await run_cases([], run_one) == []
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_eval_common_runner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval_common.runner'`

- [ ] **Step 3: Написати `runner.py`**

```python
# scripts/eval_common/runner.py
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from eval_common.models import EvalCase, EvalRun

logger = logging.getLogger(__name__)


async def run_cases(
    cases: list[EvalCase],
    run_one: Callable[[EvalCase], Awaitable[BaseModel]],
    *,
    concurrency: int = 5,
    min_interval_s: float = 0.0,
) -> list[EvalRun]:
    """Run the SUT (run_one) over each case concurrently; isolate per-case failures."""
    sem = asyncio.Semaphore(concurrency)

    async def _run(case: EvalCase) -> EvalRun:
        async with sem:
            start = time.monotonic()
            result: BaseModel | None
            try:
                result = await run_one(case)
                error = None
            except Exception as exc:  # ізоляція: падіння одного case не валить прогін
                logger.warning("run_one failed: case=%s err=%s", case.id, type(exc).__name__)
                result = None
                error = type(exc).__name__
            latency = time.monotonic() - start
            if min_interval_s:
                await asyncio.sleep(min_interval_s)
            return EvalRun(case=case, result=result, latency_s=latency, error=error)

    return list(await asyncio.gather(*(_run(c) for c in cases)))
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_eval_common_runner.py -q`
Expected: PASS (2 тести)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check scripts/eval_common/runner.py tests/test_eval_common_runner.py
.venv/bin/ruff format scripts/eval_common/runner.py tests/test_eval_common_runner.py
git add scripts/eval_common/runner.py tests/test_eval_common_runner.py
git commit -m "feat(eval-common): run_cases — конкурентний раннер з ізоляцією помилок"
```

---

### Task 6: `report.py` — `write_report`

**Files:**
- Create: `scripts/eval_common/report.py`
- Test: `tests/test_eval_common_report.py`

Ключовий тест — `SerializeAsAny`: поля сабкласу `input`/`metrics` мають вижити в `report.json`.

- [ ] **Step 1: Написати падаючі тести**

```python
# tests/test_eval_common_report.py
import json

from pydantic import BaseModel

from eval_common.models import (
    EvalCase,
    EvalMetadata,
    EvalReport,
    EvalRun,
    ScoreCard,
    ScoredRun,
)
from eval_common.report import write_report


class _In(BaseModel):
    question: str


class _M(BaseModel):
    mean: float


def _report() -> EvalReport:
    case = EvalCase(id="1", input=_In(question="що?"))
    run = EvalRun(case=case, result=None, latency_s=0.1, error=None)
    scored = ScoredRun(run=run, cards=[ScoreCard(scorer="x", score=1.0)])
    return EvalReport(
        metadata=EvalMetadata(eval_name="t", created_at="2026-01-01T00:00:00Z", n_cases=1),
        metrics=_M(mean=0.5),
        runs=[scored],
    )


def test_write_report_persists_subclass_fields(tmp_path):
    write_report(_report(), tmp_path)
    data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    # SerializeAsAny: поле сабкласу вижило
    assert data["runs"][0]["run"]["case"]["input"]["question"] == "що?"
    assert data["metrics"]["mean"] == 0.5


def test_write_report_md_has_header(tmp_path):
    write_report(_report(), tmp_path)
    md = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "t" in md  # eval_name
    assert "cases: 1" in md
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_eval_common_report.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval_common.report'`

- [ ] **Step 3: Написати `report.py`**

```python
# scripts/eval_common/report.py
from __future__ import annotations

from pathlib import Path

from eval_common.models import EvalReport


def write_report(report: EvalReport, out_dir: Path) -> None:
    """Persist both report.json (full per-item) and report.md (human summary)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(_render_md(report), encoding="utf-8")


def _render_md(report: EvalReport) -> str:
    m = report.metadata
    lines = [
        f"# {m.eval_name} — eval report",
        "",
        f"- created: {m.created_at}",
        f"- cases: {m.n_cases}",
        f"- judge: {m.judge_id or '—'}",
        "",
        "## Metrics",
        "",
        "```json",
        report.metrics.model_dump_json(indent=2),
        "```",
        "",
        f"_{len(report.runs)} per-item runs persisted in report.json._",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_eval_common_report.py -q`
Expected: PASS (2 тести)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check scripts/eval_common/report.py tests/test_eval_common_report.py
.venv/bin/ruff format scripts/eval_common/report.py tests/test_eval_common_report.py
git add scripts/eval_common/report.py tests/test_eval_common_report.py
git commit -m "feat(eval-common): write_report (JSON+MD, SerializeAsAny-safe)"
```

---

### Task 7: `__init__.py` — `run_eval` + ре-експорт

**Files:**
- Modify: `scripts/eval_common/__init__.py`
- Test: `tests/test_eval_common_run_eval.py`

- [ ] **Step 1: Написати падаючий інтеграційний тест**

```python
# tests/test_eval_common_run_eval.py
from pydantic import BaseModel

from eval_common import run_eval
from eval_common.models import EvalCase, EvalMetadata, ScoreCard


class _In(BaseModel):
    n: int


class _Out(BaseModel):
    doubled: int


class _M(BaseModel):
    total: int


class _SumScorer:
    name = "sum"

    async def score(self, run):
        return ScoreCard(scorer=self.name, score=float(run.result.doubled))


async def test_run_eval_end_to_end(tmp_path):
    cases = [EvalCase(id=str(i), input=_In(n=i)) for i in range(3)]

    async def run_one(case):
        return _Out(doubled=case.input.n * 2)

    def aggregate(scored):
        return _M(total=int(sum(c.score for s in scored for c in s.cards)))

    meta = EvalMetadata(eval_name="t", created_at="2026-01-01T00:00:00Z", n_cases=3)
    report = await run_eval(cases, run_one, [_SumScorer()], aggregate, meta, tmp_path)

    assert report.metrics.total == 0 + 2 + 4
    assert len(report.runs) == 3
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_eval_common_run_eval.py -q`
Expected: FAIL — `ImportError: cannot import name 'run_eval' from 'eval_common'`

- [ ] **Step 3: Наповнити `__init__.py`**

```python
# scripts/eval_common/__init__.py
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from pydantic import BaseModel

from eval_common.models import (
    EvalCase,
    EvalMetadata,
    EvalReport,
    EvalRun,
    ScoreCard,
    ScoredRun,
)
from eval_common.protocols import Scorer
from eval_common.report import write_report
from eval_common.runner import run_cases

__all__ = [
    "EvalCase",
    "EvalRun",
    "ScoreCard",
    "ScoredRun",
    "EvalMetadata",
    "EvalReport",
    "Scorer",
    "run_cases",
    "write_report",
    "run_eval",
]


async def run_eval(
    cases: list[EvalCase],
    run_one: Callable[[EvalCase], Awaitable[BaseModel]],
    scorers: list[Scorer],
    aggregate: Callable[[list[ScoredRun]], BaseModel],
    metadata: EvalMetadata,
    out_dir: Path,
    *,
    concurrency: int = 5,
) -> EvalReport:
    """Single-pass eval: run SUT → score each run → aggregate → write report."""
    runs = await run_cases(cases, run_one, concurrency=concurrency)
    scored: list[ScoredRun] = []
    for run in runs:
        cards = await asyncio.gather(*(s.score(run) for s in scorers))
        scored.append(ScoredRun(run=run, cards=list(cards)))
    metrics = aggregate(scored)
    report = EvalReport(metadata=metadata, metrics=metrics, runs=scored)
    write_report(report, out_dir)
    return report
```

- [ ] **Step 4: Запустити — інтеграційний + уся сюїта eval_common**

Run: `.venv/bin/python -m pytest tests/test_eval_common_run_eval.py -q`
Expected: PASS (1 тест)

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (уся сюїта, наявні + нові eval_common)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check scripts/eval_common/__init__.py tests/test_eval_common_run_eval.py
.venv/bin/ruff format scripts/eval_common/__init__.py tests/test_eval_common_run_eval.py
git add scripts/eval_common/__init__.py tests/test_eval_common_run_eval.py
git commit -m "feat(eval-common): run_eval() оркестрація + публічний ре-експорт"
```

---

## Self-Review

**Spec coverage** (дизайн §-секції → задача):
- Ролі/типи (§Типи) → Task 1 ✓; Runner (§Контракти) → Task 5 ✓; Scorer/Judge Protocol + гігієна → Task 3/4 ✓;
  Reporter → Task 6 ✓; `run_eval` гібрид → Task 7 ✓; clients/`build_eval_llm` → Task 2 ✓; фейки → Task 4 ✓.
- Обробка помилок (ізоляція в Runner) → Task 5 тест ✓. Concurrency (semaphore) → Task 5 ✓.
- **Свідомо відкладено** (узгоджено в дизайні «поза скоупом»): персист `EvalRun[]`/`--stages`,
  калібрування судді, ретрофіт наявних евалів, throttle-таблиці, cost-трекінг.

**Type consistency:** `run_one: Callable[[EvalCase], Awaitable[BaseModel]]` однаково в Task 5 і 7;
`Scorer.score(run)->ScoreCard` у Task 4 і вжито в Task 7; `write_report(report, out_dir)` Task 6 і 7;
`EvalReport(metadata, metrics, runs)` Task 1 і 7. Узгоджено.

**Placeholder scan:** повний код у кожному кроці; реальні команди + очікуваний вивід. Без TBD/«додати обробку».

**Відоме обмеження v1 (не плейсхолдер, свідомо):** scorer-фан-аут у `run_eval` — `gather` по скорерах
у межах одного run (judge-concurrency ≈ к-сть скорерів, мала й природно обмежена); рани скоряться
послідовно. Тонший контроль concurrency скоринга — коли з'явиться потреба (rule of three).

---

## Execution Handoff

Plan complete. Два варіанти виконання:

1. **Subagent-Driven (рекомендовано)** — свіжий субагент на задачу, рев'ю між задачами.
2. **Inline** — виконую задачі в цій сесії з чекпоінтами.

Який підхід?
