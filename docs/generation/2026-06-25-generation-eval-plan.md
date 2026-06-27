# Generation Eval (v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Збудувати generation-eval (faithfulness + refusal + completeness) на каркасі `eval_common`, що оцінює реальний `AnswerOrchestrator` поверх UA-gold.

**Architecture:** Консумер `eval_common`: власні Pydantic-сабтайпи + 3 скорери (через `Judge` Protocol) + `aggregate` + gold-білдер. `generation_eval.py` (CLI) кличе реальний `AnswerOrchestrator` як `run_one` і передає все в `run_eval`. Скорери/aggregate юніт-тестуються з `FakeJudge`; кінцевий прогін — ручний (реальна інфра).

**Tech Stack:** Python 3.14, Pydantic v2, `eval_common`, LiteLLM (`LLMJudge`), pytest (`asyncio_mode=auto`), ruff.

**Design:** [`2026-06-25-generation-eval-design.md`](2026-06-25-generation-eval-design.md)

---

## File Structure

```
scripts/generation/
  __init__.py            # пакет                                            [Task 1]
  gen_models.py          # GenerationInput/Labels/Metrics + detail-сабмоделі [Task 1]
  judge_prompts.py       # промпти + парсери + render_sources                [Task 2]
  scorers.py             # Faithfulness/Refusal/Completeness Scorer          [Task 3]
  metrics.py             # aggregate(scored) → GenerationMetrics             [Task 4]
  gold.py                # generation_gold.json → list[EvalCase]             [Task 5]
  build_generation_gold.py  # retrieval-gold + manual → generation_gold.json [Task 6]
  generation_eval.py     # main CLI (manual integration run)                 [Task 8]
scripts/data/
  generation_manual_questions.json  # ручний (synthesis + off-corpus)        [Task 7]
tests/
  test_generation_judge_prompts.py  [Task 2]
  test_generation_scorers.py        [Task 3]
  test_generation_metrics.py        [Task 4]
  test_generation_gold.py           [Task 5]
  test_build_generation_gold.py     [Task 6]
```

Пакет під `scripts/` → імпорт як `generation.X` (як `extraction.X`/`retrieval.X`). Чисті Pydantic-моделі НЕ юніт-тестуємо (CLAUDE.md). Коміти укр. conventional; трейлер `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: пакет + `gen_models.py`

**Files:**
- Create: `scripts/generation/__init__.py` (порожній)
- Create: `scripts/generation/gen_models.py`

Чисті Pydantic-моделі — без юніт-тесту (серіалізацію покриває `eval_common` через `SerializeAsAny`).

- [ ] **Step 1: порожній пакетний init**

Create `scripts/generation/__init__.py` (empty file).

- [ ] **Step 2: написати `gen_models.py`**

```python
# scripts/generation/gen_models.py
from __future__ import annotations

from pydantic import BaseModel


class GenerationInput(BaseModel):
    question: str
    limit: int = 10


class ExpectedSource(BaseModel):
    prediction_id: str
    claim: str


class GenerationLabels(BaseModel):
    answerable: bool
    expected_sources: list[ExpectedSource] = []
    category: str  # single_source | synthesis | off_domain | near_domain


class ClaimVerdict(BaseModel):
    claim: str
    supported: bool
    reason: str = ""


class FaithfulnessDetail(BaseModel):
    claims: list[ClaimVerdict]


class RefusalDetail(BaseModel):
    refused: bool
    answerable: bool
    category: str


class SourceCoverage(BaseModel):
    prediction_id: str
    covered: bool
    reason: str = ""


class CompletenessDetail(BaseModel):
    coverage: list[SourceCoverage]


class CategoryMetrics(BaseModel):
    n: int
    faithfulness_mean: float | None
    recall_mean: float | None
    refusal_accuracy: float


class GenerationMetrics(BaseModel):
    n_total: int
    n_answered: int
    n_refused: int
    n_errors: int
    faithfulness_mean: float | None
    hallucination_rate: float | None
    recall_mean: float | None
    refusal_accuracy: float
    over_refusal_rate: float
    false_answer_rate: float
    by_category: dict[str, CategoryMetrics]
```

- [ ] **Step 3: перевірити імпорт**

Run: `PYTHONPATH=scripts .venv/bin/python -c "import generation.gen_models as m; print(m.GenerationLabels, m.GenerationMetrics)"`
Expected: друкує класи без помилок.

- [ ] **Step 4: lint + commit**

```bash
.venv/bin/ruff check scripts/generation/ && .venv/bin/ruff format scripts/generation/
git add scripts/generation/__init__.py scripts/generation/gen_models.py
git commit -m "feat(generation-eval): доменні типи (Input/Labels/details/Metrics)"
```

---

### Task 2: `judge_prompts.py` — промпти + парсери + render_sources

**Files:**
- Create: `scripts/generation/judge_prompts.py`
- Test: `tests/test_generation_judge_prompts.py`

Тестуємо логіку: `_extract_json`, три парсери, `render_sources`. Самі шаблони промптів — константи.

- [ ] **Step 1: написати падаючі тести**

```python
# tests/test_generation_judge_prompts.py
from datetime import date

from generation.judge_prompts import (
    parse_completeness_response,
    parse_faithfulness_response,
    parse_refusal_response,
    render_sources,
)
from prophet_checker.models.domain import (
    Prediction,
    PredictionStatus,
    RetrievedPrediction,
)


def test_parse_faithfulness_response_plain_and_fenced():
    raw = '{"claims": [{"claim": "a", "supported": true, "reason": "r"}, {"claim": "b", "supported": false}]}'
    claims = parse_faithfulness_response(raw)
    assert len(claims) == 2
    assert claims[0].claim == "a" and claims[0].supported is True
    assert claims[1].supported is False
    fenced = "```json\n{\"claims\": []}\n```"
    assert parse_faithfulness_response(fenced) == []


def test_parse_refusal_response():
    assert parse_refusal_response('{"refused": true}') is True
    assert parse_refusal_response('{"refused": false}') is False


def test_parse_completeness_response():
    covered, reason = parse_completeness_response('{"covered": true, "reason": "так"}')
    assert covered is True and reason == "так"
    covered, _ = parse_completeness_response('{"covered": false}')
    assert covered is False


def test_render_sources_includes_id_claim_status():
    pred = Prediction(
        id="p1",
        document_id="d",
        person_id="x",
        claim_text="контрнаступ не дійде до моря",
        situation="південь",
        prediction_date=date(2023, 6, 1),
        status=PredictionStatus.REFUTED,
    )
    text = render_sources([RetrievedPrediction(prediction=pred, distance=0.2, rank=1)])
    assert "p1" in text
    assert "контрнаступ не дійде до моря" in text
    assert "refuted" in text
```

- [ ] **Step 2: запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_generation_judge_prompts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'generation.judge_prompts'`

- [ ] **Step 3: написати `judge_prompts.py`**

```python
# scripts/generation/judge_prompts.py
from __future__ import annotations

import json
import re

from generation.gen_models import ClaimVerdict

_FENCE_RE = re.compile(r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)

FAITHFULNESS_SYSTEM = (
    "Ти — суворий фактчекер. Розкладаєш ВІДПОВІДЬ на атомарні фактичні твердження "
    "й перевіряєш кожне проти наданих ДЖЕРЕЛ. Відповідаєш ЛИШЕ валідним JSON."
)
REFUSAL_SYSTEM = (
    "Визначаєш, чи текст є відмовою відповісти за браком даних. Відповідаєш ЛИШЕ JSON."
)
COMPLETENESS_SYSTEM = (
    "Визначаєш, чи конкретне ТВЕРДЖЕННЯ відображене у ВІДПОВІДІ. Відповідаєш ЛИШЕ JSON."
)


def _extract_json(text: str) -> dict:
    m = _FENCE_RE.match(text.strip())
    payload = m.group(1) if m else text
    return json.loads(payload)


def render_sources(sources: list) -> str:
    lines = []
    for s in sources:
        p = s.prediction
        situation = f" | {p.situation}" if p.situation else ""
        lines.append(f"[{p.id}] {p.claim_text}{situation} (status: {p.status.value})")
    return "\n".join(lines)


def build_faithfulness_prompt(answer: str, sources: list) -> str:
    return (
        "Розклади ВІДПОВІДЬ на атомарні фактичні твердження. Для кожного визнач, чи воно "
        "підкріплене ДЖЕРЕЛАМИ (supported true/false). Якщо ВІДПОВІДЬ — відмова або не містить "
        'фактів, поверни порожній список. Формат: {"claims": [{"claim": "...", '
        '"supported": true, "reason": "..."}]}\n\n'
        f"ВІДПОВІДЬ:\n{answer}\n\nДЖЕРЕЛА:\n{render_sources(sources)}"
    )


def build_refusal_prompt(answer: str) -> str:
    return (
        "Чи ВІДПОВІДЬ є відмовою відповісти (каже, що не може / немає даних)? "
        'Формат: {"refused": true|false}\n\n'
        f"ВІДПОВІДЬ:\n{answer}"
    )


def build_completeness_prompt(answer: str, claim: str) -> str:
    return (
        "Чи ВІДПОВІДЬ відображає (згадує або передає суть) ТВЕРДЖЕННЯ? "
        'Формат: {"covered": true|false, "reason": "..."}\n\n'
        f"ТВЕРДЖЕННЯ:\n{claim}\n\nВІДПОВІДЬ:\n{answer}"
    )


def parse_faithfulness_response(text: str) -> list[ClaimVerdict]:
    data = _extract_json(text)
    return [
        ClaimVerdict(claim=c["claim"], supported=bool(c["supported"]), reason=c.get("reason", ""))
        for c in data.get("claims", [])
    ]


def parse_refusal_response(text: str) -> bool:
    return bool(_extract_json(text)["refused"])


def parse_completeness_response(text: str) -> tuple[bool, str]:
    data = _extract_json(text)
    return bool(data["covered"]), data.get("reason", "")
```

- [ ] **Step 4: запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_generation_judge_prompts.py -q`
Expected: PASS (4 тести)

- [ ] **Step 5: lint + commit**

```bash
.venv/bin/ruff check scripts/generation/judge_prompts.py tests/test_generation_judge_prompts.py
.venv/bin/ruff format scripts/generation/judge_prompts.py tests/test_generation_judge_prompts.py
git add scripts/generation/judge_prompts.py tests/test_generation_judge_prompts.py
git commit -m "feat(generation-eval): judge-промпти + парсери + render_sources"
```

---

### Task 3: `scorers.py` — три скорери

**Files:**
- Create: `scripts/generation/scorers.py`
- Test: `tests/test_generation_scorers.py`

- [ ] **Step 1: написати падаючі тести**

```python
# tests/test_generation_scorers.py
from datetime import date

from eval_common.models import EvalCase, EvalRun, ScoreCard
from generation.gen_models import ExpectedSource, GenerationInput, GenerationLabels
from generation.scorers import CompletenessScorer, FaithfulnessScorer, RefusalScorer
from prophet_checker.models.domain import AnswerResult, Prediction, RetrievedPrediction
from prophet_checker.query.answer_orchestrator import REFUSAL_NO_DATA


class _SeqJudge:
    """Повертає задані відповіді по черзі (для різних вердиктів на послідовні виклики)."""

    id = "seq"

    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self._i = 0

    async def assess(self, prompt: str, *, system: str) -> str:
        r = self._responses[self._i]
        self._i += 1
        return r


def _pred(pid: str) -> Prediction:
    return Prediction(
        id=pid, document_id="d", person_id="x", claim_text=f"claim {pid}", prediction_date=date(2024, 1, 1)
    )


def _run(answer: str | None, *, answerable: bool, category: str, expected: list[ExpectedSource] | None = None):
    labels = GenerationLabels(answerable=answerable, expected_sources=expected or [], category=category)
    case = EvalCase(id="c1", input=GenerationInput(question="q"), labels=labels)
    result = None
    if answer is not None:
        result = AnswerResult(
            query="q",
            answer=answer,
            sources=[RetrievedPrediction(prediction=_pred("p1"), distance=0.1, rank=1)],
        )
    return EvalRun(case=case, result=result, latency_s=0.1)


# --- faithfulness ---

async def test_faithfulness_na_on_sut_error():
    card = await FaithfulnessScorer(_SeqJudge()).score(_run(None, answerable=True, category="single_source"))
    assert card.score is None


async def test_faithfulness_na_on_offcorpus():
    judge = _SeqJudge('{"claims": [{"claim": "x", "supported": true}]}')
    card = await FaithfulnessScorer(judge).score(_run("щось", answerable=False, category="off_domain"))
    assert card.score is None


async def test_faithfulness_na_on_zero_claims():
    judge = _SeqJudge('{"claims": []}')
    card = await FaithfulnessScorer(judge).score(_run(REFUSAL_NO_DATA, answerable=True, category="single_source"))
    assert card.score is None


async def test_faithfulness_ratio():
    judge = _SeqJudge('{"claims": [{"claim": "a", "supported": true}, {"claim": "b", "supported": false}]}')
    card = await FaithfulnessScorer(judge).score(_run("відп", answerable=True, category="single_source"))
    assert card.score == 0.5
    assert len(card.detail.claims) == 2


# --- refusal ---

async def test_refusal_na_on_sut_error():
    card = await RefusalScorer(_SeqJudge()).score(_run(None, answerable=True, category="single_source"))
    assert card.score is None


async def test_refusal_hardrefusal_on_answerable_is_wrong():
    card = await RefusalScorer(_SeqJudge()).score(
        _run(REFUSAL_NO_DATA, answerable=True, category="single_source")
    )
    assert card.score == 0.0  # over-refusal
    assert card.detail.refused is True


async def test_refusal_hardrefusal_on_offcorpus_is_correct():
    card = await RefusalScorer(_SeqJudge()).score(_run(REFUSAL_NO_DATA, answerable=False, category="off_domain"))
    assert card.score == 1.0


async def test_refusal_soft_refusal_via_judge():
    judge = _SeqJudge('{"refused": true}')
    card = await RefusalScorer(judge).score(_run("не можу відповісти", answerable=False, category="near_domain"))
    assert card.score == 1.0


async def test_refusal_false_answer_on_offcorpus():
    judge = _SeqJudge('{"refused": false}')
    card = await RefusalScorer(judge).score(_run("впевнена вигадка", answerable=False, category="off_domain"))
    assert card.score == 0.0


# --- completeness ---

async def test_completeness_na_on_offcorpus():
    card = await CompletenessScorer(_SeqJudge()).score(_run("щось", answerable=False, category="off_domain"))
    assert card.score is None


async def test_completeness_recall_half():
    expected = [ExpectedSource(prediction_id="p1", claim="c1"), ExpectedSource(prediction_id="p2", claim="c2")]
    judge = _SeqJudge('{"covered": true}', '{"covered": false}')
    card = await CompletenessScorer(judge).score(
        _run("відп", answerable=True, category="synthesis", expected=expected)
    )
    assert card.score == 0.5
    assert [c.covered for c in card.detail.coverage] == [True, False]
```

- [ ] **Step 2: запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_generation_scorers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'generation.scorers'`

- [ ] **Step 3: написати `scorers.py`**

```python
# scripts/generation/scorers.py
from __future__ import annotations

from eval_common.judge import Judge
from eval_common.models import EvalRun, ScoreCard
from generation.gen_models import (
    CompletenessDetail,
    FaithfulnessDetail,
    RefusalDetail,
    SourceCoverage,
)
from generation.judge_prompts import (
    COMPLETENESS_SYSTEM,
    FAITHFULNESS_SYSTEM,
    REFUSAL_SYSTEM,
    build_completeness_prompt,
    build_faithfulness_prompt,
    build_refusal_prompt,
    parse_completeness_response,
    parse_faithfulness_response,
    parse_refusal_response,
)
from prophet_checker.query.answer_orchestrator import REFUSAL_NO_DATA


class FaithfulnessScorer:
    name = "faithfulness"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    async def score(self, run: EvalRun) -> ScoreCard:
        labels = run.case.labels
        if run.result is None or not labels.answerable:
            return ScoreCard(scorer=self.name, score=None)
        prompt = build_faithfulness_prompt(run.result.answer, run.result.sources)
        raw = await self._judge.assess(prompt, system=FAITHFULNESS_SYSTEM)
        claims = parse_faithfulness_response(raw)
        if not claims:  # відмова / нефактична відповідь → N/A
            return ScoreCard(scorer=self.name, score=None)
        supported = sum(1 for c in claims if c.supported)
        return ScoreCard(
            scorer=self.name,
            score=supported / len(claims),
            detail=FaithfulnessDetail(claims=claims),
        )


class RefusalScorer:
    name = "refusal"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    async def score(self, run: EvalRun) -> ScoreCard:
        labels = run.case.labels
        if run.result is None:
            return ScoreCard(scorer=self.name, score=None)
        answer = run.result.answer
        if answer.strip() == REFUSAL_NO_DATA:
            refused = True
        else:
            raw = await self._judge.assess(build_refusal_prompt(answer), system=REFUSAL_SYSTEM)
            refused = parse_refusal_response(raw)
        correct = (labels.answerable and not refused) or (not labels.answerable and refused)
        return ScoreCard(
            scorer=self.name,
            score=1.0 if correct else 0.0,
            detail=RefusalDetail(refused=refused, answerable=labels.answerable, category=labels.category),
        )


class CompletenessScorer:
    name = "completeness"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    async def score(self, run: EvalRun) -> ScoreCard:
        labels = run.case.labels
        if run.result is None or not labels.answerable or not labels.expected_sources:
            return ScoreCard(scorer=self.name, score=None)
        coverage = []
        for es in labels.expected_sources:
            raw = await self._judge.assess(
                build_completeness_prompt(run.result.answer, es.claim), system=COMPLETENESS_SYSTEM
            )
            covered, reason = parse_completeness_response(raw)
            coverage.append(SourceCoverage(prediction_id=es.prediction_id, covered=covered, reason=reason))
        score = sum(1 for c in coverage if c.covered) / len(coverage)
        return ScoreCard(scorer=self.name, score=score, detail=CompletenessDetail(coverage=coverage))
```

- [ ] **Step 4: запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_generation_scorers.py -q`
Expected: PASS (11 тестів)

- [ ] **Step 5: lint + commit**

```bash
.venv/bin/ruff check scripts/generation/scorers.py tests/test_generation_scorers.py
.venv/bin/ruff format scripts/generation/scorers.py tests/test_generation_scorers.py
git add scripts/generation/scorers.py tests/test_generation_scorers.py
git commit -m "feat(generation-eval): Faithfulness/Refusal/Completeness скорери"
```

---

### Task 4: `metrics.py` — aggregate

**Files:**
- Create: `scripts/generation/metrics.py`
- Test: `tests/test_generation_metrics.py`

- [ ] **Step 1: написати падаючі тести**

```python
# tests/test_generation_metrics.py
from datetime import date

from eval_common.models import EvalCase, EvalRun, ScoreCard, ScoredRun
from generation.gen_models import GenerationInput, GenerationLabels, RefusalDetail
from generation.metrics import aggregate
from prophet_checker.models.domain import AnswerResult, Prediction, RetrievedPrediction


def _pred():
    return Prediction(id="p", document_id="d", person_id="x", claim_text="c", prediction_date=date(2024, 1, 1))


def _scored(category, answerable, *, faith=None, recall=None, refused=False, error=False):
    labels = GenerationLabels(answerable=answerable, category=category)
    case = EvalCase(id="c", input=GenerationInput(question="q"), labels=labels)

    if error:
        run = EvalRun(case=case, result=None, latency_s=0.1, error="RuntimeError")
        cards = [ScoreCard(scorer=name, score=None) for name in ("faithfulness", "refusal", "completeness")]
        return ScoredRun(run=run, cards=cards)

    result = AnswerResult(
        query="q", answer="a", sources=[RetrievedPrediction(prediction=_pred(), distance=0.1, rank=1)]
    )
    run = EvalRun(case=case, result=result, latency_s=0.1)
    correct = (answerable and not refused) or (not answerable and refused)
    cards = [
        ScoreCard(scorer="faithfulness", score=faith),
        ScoreCard(
            scorer="refusal",
            score=1.0 if correct else 0.0,
            detail=RefusalDetail(refused=refused, answerable=answerable, category=category),
        ),
        ScoreCard(scorer="completeness", score=recall),
    ]
    return ScoredRun(run=run, cards=cards)


def test_aggregate_means_and_refusal_rates():
    scored = [
        _scored("single_source", True, faith=1.0, recall=1.0, refused=False),
        _scored("single_source", True, faith=0.5, recall=0.0, refused=False),
        _scored("off_domain", False, refused=True),                  # correct refusal
        _scored("near_domain", False, refused=False),                # false answer
        _scored("single_source", True, error=True),                  # SUT error
    ]
    m = aggregate(scored)
    assert m.n_total == 5
    assert m.n_errors == 1
    assert m.n_answered == 3   # 2 answerable answered + 1 off-corpus answered
    assert m.n_refused == 1
    assert m.faithfulness_mean == 0.75
    assert m.hallucination_rate == 0.25
    assert m.recall_mean == 0.5
    # refusal: 2 answerable answered (correct), 1 off refused (correct), 1 off answered (wrong) = 3/4
    assert m.refusal_accuracy == 0.75
    assert m.over_refusal_rate == 0.0           # no answerable refused
    assert m.false_answer_rate == 0.5           # 1 of 2 off-corpus answered
    assert m.by_category["single_source"].faithfulness_mean == 0.75


def test_aggregate_empty():
    m = aggregate([])
    assert m.n_total == 0
    assert m.faithfulness_mean is None
    assert m.refusal_accuracy == 0.0
```

- [ ] **Step 2: запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_generation_metrics.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'generation.metrics'`

- [ ] **Step 3: написати `metrics.py`**

```python
# scripts/generation/metrics.py
from __future__ import annotations

from eval_common.models import ScoredRun
from generation.gen_models import CategoryMetrics, GenerationMetrics


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _cards(run) -> dict:
    return {c.scorer: c for c in run.cards}


def aggregate(scored: list[ScoredRun]) -> GenerationMetrics:
    n_total = len(scored)
    n_errors = sum(1 for s in scored if s.run.result is None)

    faith: list[float] = []
    recall: list[float] = []
    refusal_scores: list[float] = []
    n_answered = n_refused = 0
    over_num = over_den = false_num = false_den = 0
    by_cat: dict[str, dict[str, list]] = {}

    for s in scored:
        cat = s.run.case.labels.category
        bucket = by_cat.setdefault(cat, {"faith": [], "recall": [], "refusal": [], "n": 0})
        bucket["n"] += 1
        cards = _cards(s)

        f = cards.get("faithfulness")
        if f is not None and f.score is not None:
            faith.append(f.score)
            bucket["faith"].append(f.score)

        c = cards.get("completeness")
        if c is not None and c.score is not None:
            recall.append(c.score)
            bucket["recall"].append(c.score)

        r = cards.get("refusal")
        if r is not None and r.score is not None:
            refusal_scores.append(r.score)
            bucket["refusal"].append(r.score)
            d = r.detail  # RefusalDetail
            if d.refused:
                n_refused += 1
            else:
                n_answered += 1
            if d.answerable:
                over_den += 1
                over_num += 1 if d.refused else 0
            else:
                false_den += 1
                false_num += 1 if not d.refused else 0

    faithfulness_mean = _mean(faith)
    by_category = {
        cat: CategoryMetrics(
            n=b["n"],
            faithfulness_mean=_mean(b["faith"]),
            recall_mean=_mean(b["recall"]),
            refusal_accuracy=_mean(b["refusal"]) or 0.0,
        )
        for cat, b in by_cat.items()
    }
    return GenerationMetrics(
        n_total=n_total,
        n_answered=n_answered,
        n_refused=n_refused,
        n_errors=n_errors,
        faithfulness_mean=faithfulness_mean,
        hallucination_rate=(1 - faithfulness_mean) if faithfulness_mean is not None else None,
        recall_mean=_mean(recall),
        refusal_accuracy=_mean(refusal_scores) or 0.0,
        over_refusal_rate=(over_num / over_den) if over_den else 0.0,
        false_answer_rate=(false_num / false_den) if false_den else 0.0,
        by_category=by_category,
    )
```

- [ ] **Step 4: запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_generation_metrics.py -q`
Expected: PASS (2 тести)

- [ ] **Step 5: lint + commit**

```bash
.venv/bin/ruff check scripts/generation/metrics.py tests/test_generation_metrics.py
.venv/bin/ruff format scripts/generation/metrics.py tests/test_generation_metrics.py
git add scripts/generation/metrics.py tests/test_generation_metrics.py
git commit -m "feat(generation-eval): aggregate → GenerationMetrics (per-category)"
```

---

### Task 5: `gold.py` — завантаження gold → `EvalCase[]`

**Files:**
- Create: `scripts/generation/gold.py`
- Test: `tests/test_generation_gold.py`

- [ ] **Step 1: написати падаючий тест**

```python
# tests/test_generation_gold.py
import json

from generation.gold import load_generation_gold


def test_load_generation_gold(tmp_path):
    gold = [
        {"id": "a000", "question": "q1", "answerable": True,
         "expected_sources": [{"prediction_id": "p1", "claim": "c1"}], "category": "single_source"},
        {"id": "o000", "question": "рецепт", "answerable": False,
         "expected_sources": [], "category": "off_domain"},
    ]
    path = tmp_path / "g.json"
    path.write_text(json.dumps(gold, ensure_ascii=False), encoding="utf-8")

    cases = load_generation_gold(path)
    assert len(cases) == 2
    assert cases[0].id == "a000"
    assert cases[0].input.question == "q1"
    assert cases[0].labels.answerable is True
    assert cases[0].labels.expected_sources[0].prediction_id == "p1"
    assert cases[1].labels.category == "off_domain"
```

- [ ] **Step 2: запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_generation_gold.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'generation.gold'`

- [ ] **Step 3: написати `gold.py`**

```python
# scripts/generation/gold.py
from __future__ import annotations

import json
from pathlib import Path

from eval_common.models import EvalCase
from generation.gen_models import ExpectedSource, GenerationInput, GenerationLabels


def load_generation_gold(path: Path) -> list[EvalCase]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = []
    for r in data:
        labels = GenerationLabels(
            answerable=r["answerable"],
            expected_sources=[ExpectedSource(**es) for es in r["expected_sources"]],
            category=r["category"],
        )
        cases.append(
            EvalCase(id=r["id"], input=GenerationInput(question=r["question"]), labels=labels)
        )
    return cases
```

- [ ] **Step 4: запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_generation_gold.py -q`
Expected: PASS

- [ ] **Step 5: lint + commit**

```bash
.venv/bin/ruff check scripts/generation/gold.py tests/test_generation_gold.py
.venv/bin/ruff format scripts/generation/gold.py tests/test_generation_gold.py
git add scripts/generation/gold.py tests/test_generation_gold.py
git commit -m "feat(generation-eval): gold loader → EvalCase[]"
```

---

### Task 6: `build_generation_gold.py` — білдер gold

**Files:**
- Create: `scripts/generation/build_generation_gold.py`
- Test: `tests/test_build_generation_gold.py`

Тестуємо чисту функцію `build_gold(retrieval_gold, manual, claim_by_id)`. `main()` (читання/запис файлів) — тонкий, без тесту.

- [ ] **Step 1: написати падаючий тест**

```python
# tests/test_build_generation_gold.py
import pytest

from generation.build_generation_gold import build_gold


def _retrieval():
    return [
        {"query": "claim-фраза A", "target_id": "t1", "source_field": "claim_text"},
        {"query": "situation-фраза A", "target_id": "t1", "source_field": "situation"},
        {"query": "claim-фраза B", "target_id": "t2", "source_field": "claim_text"},
        {"query": "situation-фраза B", "target_id": "t2", "source_field": "situation"},
    ]


def _claims():
    return {"t1": "клейм-1", "t2": "клейм-2", "s1": "синтез-клейм"}


def test_build_gold_single_source_5050_and_enrichment():
    manual = [
        {"question": "синтез?", "category": "synthesis", "prediction_ids": ["t1", "s1"]},
        {"question": "рецепт борщу", "category": "off_domain", "prediction_ids": []},
    ]
    out = build_gold(_retrieval(), manual, _claims())

    single = [r for r in out if r["category"] == "single_source"]
    assert len(single) == 2
    # 50/50: t1 (idx0) → claim-фраза, t2 (idx1) → situation-фраза
    by_tid = {r["expected_sources"][0]["prediction_id"]: r for r in single}
    assert by_tid["t1"]["question"] == "claim-фраза A"
    assert by_tid["t2"]["question"] == "situation-фраза B"
    assert by_tid["t1"]["expected_sources"][0]["claim"] == "клейм-1"  # збагачено

    syn = next(r for r in out if r["category"] == "synthesis")
    assert syn["answerable"] is True
    assert {e["prediction_id"] for e in syn["expected_sources"]} == {"t1", "s1"}
    assert {e["claim"] for e in syn["expected_sources"]} == {"клейм-1", "синтез-клейм"}

    off = next(r for r in out if r["category"] == "off_domain")
    assert off["answerable"] is False
    assert off["expected_sources"] == []


def test_build_gold_failloud_on_unknown_prediction():
    manual = [{"question": "x", "category": "synthesis", "prediction_ids": ["NOPE"]}]
    with pytest.raises(KeyError):
        build_gold(_retrieval(), manual, _claims())
```

- [ ] **Step 2: запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_build_generation_gold.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'generation.build_generation_gold'`

- [ ] **Step 3: написати `build_generation_gold.py`**

```python
# scripts/generation/build_generation_gold.py
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA = PROJECT_ROOT / "scripts" / "data"


def build_gold(retrieval_gold: list[dict], manual: list[dict], claim_by_id: dict[str, str]) -> list[dict]:
    """Pure transform: retrieval-gold + manual questions + corpus claims → gold records."""
    by_target: dict[str, dict[str, str]] = {}
    for e in retrieval_gold:
        by_target.setdefault(e["target_id"], {})[e["source_field"]] = e["query"]

    out: list[dict] = []
    for i, tid in enumerate(sorted(by_target)):
        phr = by_target[tid]
        prefer = "claim_text" if i % 2 == 0 else "situation"
        other = "situation" if prefer == "claim_text" else "claim_text"
        out.append({
            "id": f"a{i:03d}",
            "question": phr.get(prefer) or phr[other],
            "answerable": True,
            "expected_sources": [{"prediction_id": tid, "claim": claim_by_id[tid]}],
            "category": "single_source",
        })

    s = o = 0
    for m in manual:
        answerable = m["category"] == "synthesis"
        if answerable:
            cid, s = f"s{s:03d}", s + 1
            expected = [{"prediction_id": p, "claim": claim_by_id[p]} for p in m["prediction_ids"]]
        else:
            cid, o = f"o{o:03d}", o + 1
            expected = []
        out.append({
            "id": cid,
            "question": m["question"],
            "answerable": answerable,
            "expected_sources": expected,
            "category": m["category"],
        })
    return out


def main() -> None:
    retrieval_gold = json.loads((DATA / "retrieval_query_gold.json").read_text(encoding="utf-8"))
    manual = json.loads((DATA / "generation_manual_questions.json").read_text(encoding="utf-8"))
    corpus = json.loads((DATA / "retrieval_eval_corpus.json").read_text(encoding="utf-8"))
    claim_by_id = {p["id"]: p["claim_text"] for p in corpus}

    gold = build_gold(retrieval_gold, manual, claim_by_id)
    out_path = DATA / "generation_gold.json"
    out_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(gold)} cases → {out_path}")


if __name__ == "__main__":
    main()
```

(Якщо `retrieval_eval_corpus.json` має іншу форму ключів — звірити поля `id`/`claim_text` на момент імплементації; `build_gold` від форми файлу не залежить.)

- [ ] **Step 4: запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_build_generation_gold.py -q`
Expected: PASS (2 тести)

- [ ] **Step 5: lint + commit**

```bash
.venv/bin/ruff check scripts/generation/build_generation_gold.py tests/test_build_generation_gold.py
.venv/bin/ruff format scripts/generation/build_generation_gold.py tests/test_build_generation_gold.py
git add scripts/generation/build_generation_gold.py tests/test_build_generation_gold.py
git commit -m "feat(generation-eval): build_generation_gold (50/50 + enrichment + fail-loud)"
```

---

### Task 7: `generation_manual_questions.json` — ручний контент (data + user review)

**Files:**
- Create: `scripts/data/generation_manual_questions.json`

Це **дані, не код** — authoring + людський рев'ю (TDD не застосовний). «Тест» = валідація build-скрипта (`prediction_ids` існують у корпусі) + рев'ю користувача.

- [ ] **Step 1: дослідити корпус для synthesis-наборів**

Run: `.venv/bin/python -c "import json; d=json.load(open('scripts/data/retrieval_eval_corpus.json')); [print(p['id'], p['claim_text'][:70]) for p in d[:200]]"`
Мета: знайти ~12 наборів по 2-3 прогнози, що природно об'єднуються темою (контрнаступ, флот, Маріуполь, мобілізація, перемовини).

- [ ] **Step 2: написати файл** `scripts/data/generation_manual_questions.json`

Схема — список `{question, category, prediction_ids}`:
- ~12 `synthesis`: ширше UA-питання, що **спанить 2-3 КОНКРЕТНІ** `prediction_ids` із корпусу.
- ~20 off-corpus з `prediction_ids: []`: ~10 `off_domain` (рецепти, спорт, кіно) + ~10 `near_domain` (правдоподібні воєнно-політичні питання, яких **нема** в корпусі — напр. про події після останнього прогнозу).

Стартовий приклад off-corpus (доповнити до ~20):
```json
[
  {"question": "Який рецепт класичного українського борщу?", "category": "off_domain", "prediction_ids": []},
  {"question": "Хто отримав Оскар за найкращий фільм у 2019 році?", "category": "off_domain", "prediction_ids": []},
  {"question": "Що Арестович прогнозував про ціни на нерухомість у Польщі на 2027 рік?", "category": "near_domain", "prediction_ids": []}
]
```

- [ ] **Step 3: рев'ю користувача** — показати повний файл; UA-human-review обов'язковий (per дослідження). Внести правки.

- [ ] **Step 4: прогнати build + перевірити валідацію**

Run: `PYTHONPATH=scripts .venv/bin/python scripts/generation/build_generation_gold.py`
Expected: `wrote ~112 cases → .../generation_gold.json` без `KeyError` (усі `prediction_ids` існують у корпусі).

- [ ] **Step 5: commit**

```bash
git add scripts/data/generation_manual_questions.json scripts/data/generation_gold.json
git commit -m "feat(generation-eval): ручні питання (synthesis + off-corpus) + build gold"
```

---

### Task 8: `generation_eval.py` — main CLI (ручна інтеграція)

**Files:**
- Create: `scripts/generation/generation_eval.py`

Без юніт-тесту (інтеграція з реальним Postgres+Gemini+Claude). Перевірка — ручний прогін (Step 3).

- [ ] **Step 1: написати `generation_eval.py`**

```python
# scripts/generation/generation_eval.py
from __future__ import annotations

import argparse
import asyncio
import logging
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path

from eval_common import EvalMetadata, run_eval
from eval_common.clients import build_eval_llm
from eval_common.judge import LLMJudge, fingerprint_prompt
from generation.gold import load_generation_gold
from generation.judge_prompts import COMPLETENESS_SYSTEM, FAITHFULNESS_SYSTEM, REFUSAL_SYSTEM
from generation.metrics import aggregate
from generation.scorers import CompletenessScorer, FaithfulnessScorer, RefusalScorer
from prophet_checker.config import Settings
from prophet_checker.factory import build_answer_orchestrator

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
GOLD_PATH = PROJECT_ROOT / "scripts" / "data" / "generation_gold.json"
OUT_DIR = PROJECT_ROOT / "scripts" / "outputs" / "generation_eval"


async def _main(judge_model: str, limit: int, concurrency: int) -> None:
    settings = Settings()
    cases = load_generation_gold(GOLD_PATH)
    judge = LLMJudge(build_eval_llm(judge_model, temperature=0), judge_id=judge_model)
    scorers = [FaithfulnessScorer(judge), RefusalScorer(judge), CompletenessScorer(judge)]

    metadata = EvalMetadata(
        eval_name="generation",
        created_at=datetime.now(UTC).isoformat(),
        n_cases=len(cases),
        sut_models={"generator": "gemini/gemini-3.1-flash-lite-preview", "embedder": settings.embedding_model},
        judge_id=judge_model,
        prompt_fingerprints={
            "faithfulness": fingerprint_prompt(FAITHFULNESS_SYSTEM),
            "refusal": fingerprint_prompt(REFUSAL_SYSTEM),
            "completeness": fingerprint_prompt(COMPLETENESS_SYSTEM),
        },
        dataset_path=str(GOLD_PATH),
    )

    async with AsyncExitStack() as stack:
        orchestrator = await build_answer_orchestrator(settings, stack)

        async def run_one(case):
            return await orchestrator.answer(case.input.question, limit=case.input.limit)

        report = await run_eval(cases, run_one, scorers, aggregate, metadata, OUT_DIR, concurrency=concurrency)

    m = report.metrics
    logger.info(
        "generation eval: n=%d faithfulness=%.3f recall=%.3f refusal_acc=%.3f false_answer=%.3f",
        m.n_total, m.faithfulness_mean or 0.0, m.recall_mean or 0.0, m.refusal_accuracy, m.false_answer_rate,
    )
    print(f"report → {OUT_DIR}/report.md  (judge-based, ще не human-calibrated)")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(description="Generation eval (faithfulness + refusal + completeness)")
    p.add_argument("--judge", default="anthropic/claude-opus-4-8")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--concurrency", type=int, default=4)
    args = p.parse_args()
    asyncio.run(_main(args.judge, args.limit, args.concurrency))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: перевірити імпорт/компіляцію**

Run: `PYTHONPATH=scripts .venv/bin/python -c "import generation.generation_eval"`
Expected: без помилок імпорту.

- [ ] **Step 3: ручний прогін** (передумови: `docker compose up -d`; backfill ембедингів; `GEMINI_API_KEY` + `OPENAI_API_KEY` + `ANTHROPIC_API_KEY` у `.env`)

Run: `PYTHONPATH=scripts .venv/bin/python scripts/generation/generation_eval.py --judge anthropic/claude-opus-4-8`
Expected: пише `scripts/outputs/generation_eval/report.{json,md}`; INFO-рядок з метриками. `report.json` несе per-claim/per-source вердикти (calibration-ready).

- [ ] **Step 4: повна юніт-сюїта лишається зеленою**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (наявні + усі нові generation-юніти; інтеграційний CLI у сюїту не входить).

- [ ] **Step 5: lint + commit**

```bash
.venv/bin/ruff check scripts/generation/generation_eval.py
.venv/bin/ruff format scripts/generation/generation_eval.py
git add scripts/generation/generation_eval.py
git commit -m "feat(generation-eval): CLI прогін поверх реального AnswerOrchestrator"
```

---

## Self-Review

**Spec coverage** (дизайн → задача): типи §Типи → T1; промпти/парсери (faithfulness combined call, render_sources) → T2; 3 скорери з N/A-логікою §Скорери → T3; aggregate per-category §Aggregate → T4; gold loader → T5; build-контракт (50/50, enrichment, fail-loud) §Gold → T6; ручний gold-контент → T7; CLI + calibration-ready metadata + caveat §Архітектура/§Calibration → T8. ✓

**Placeholder scan:** повний код у кожному кроці; реальні команди + очікуваний вивід. Task 7 — свідомий data-authoring виняток (не TDD), з валідацією через build + рев'ю.

**Type consistency:** `GenerationLabels.expected_sources: list[ExpectedSource]` — T1/T3/T5/T6 однаково; `ScoreCard(scorer, score, detail)` — скрізь із каркаса; `aggregate(scored)->GenerationMetrics` T4 = виклик у T8; `CategoryMetrics` поля T1=T4; judge `assess(prompt, *, system)` — T3 виклики = `LLMJudge` сигнатура. ✓

**Свідомо поза v1** (per дизайн): answer relevancy, citation precision/маркери, RAGChecker noise-спліт, формальне κ-калібрування, поріг релевантності.

---

## Execution Handoff

Plan complete. Два варіанти виконання:

1. **Subagent-Driven (рекомендовано)** — свіжий субагент на задачу + двостадійне рев'ю.
2. **Inline** — задачі в цій сесії з чекпоінтами.

Який підхід?
