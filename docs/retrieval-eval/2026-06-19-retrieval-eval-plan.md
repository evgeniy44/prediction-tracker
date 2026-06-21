# Retrieval Eval (RAG v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Офлайн eval-набір скриптів, що обирає embedding-модель + репрезентацію (`claim_text` / `situation` / `claim+situation`) для семантичного пошуку по прогнозах, за відносним ранжуванням (recall@k/MRR на known-item gold).

**Architecture:** Чотири незалежні скрипти в `scripts/retrieval/` + спільний адаптер сховища `eval_store.py`. Pipeline: `build_eval_corpus` (хронологічне проріджування прод-прогнозів → JSON-snapshot) → `build_query_gold` (семпл цілей + LLM-генерація 2 запитів/ціль → gold JSON) → `embed_corpus` (sweep: ембединг корпусу по кожній комбінації → eval-таблиця) → `retrieval_eval` (cosine-пошук + метрики + markdown-звіт). Чиста логіка відокремлена від I/O для unit-тестів на фейках, за конвенцією проєкту.

**Tech Stack:** Python 3.14, async SQLAlchemy, PostgreSQL + pgvector (безрозмірна eval-колонка), LiteLLM (`EmbeddingClient`/`LLMClient`), pytest (`asyncio_mode=auto`), ruff.

**Spec:** [`2026-06-19-retrieval-eval-design.md`](2026-06-19-retrieval-eval-design.md)

---

## File Structure

```
scripts/retrieval/
  __init__.py
  eval_store.py          # EVAL_TABLE_DDL + EvalEmbStore Protocol + PostgresEvalEmbStore (write/search)
  build_eval_corpus.py   # _score, thin_chronologically, load_predictions, main → retrieval_eval_corpus.json
  build_query_gold.py    # sample_targets, build_query_prompt, generate_queries, main → retrieval_query_gold.json
  embed_corpus.py        # build_representation_text, run_sweep, main (populate eval-таблицю)
  retrieval_eval.py      # recall_at_k, reciprocal_rank, aggregate_metrics, render_report, run_eval, main
scripts/data/
  retrieval_eval_corpus.json        # snapshot корпусу (вихід build_eval_corpus)
  retrieval_query_gold.json         # синтетичні запити (вихід build_query_gold)
  retrieval_query_gold_manual.json  # ручний зріз (пише людина; build_query_gold лишає шаблон)
scripts/outputs/retrieval_eval/
  retrieval_eval_report.md
tests/
  test_retrieval_thinning.py
  test_retrieval_corpus_io.py
  test_retrieval_sampling.py
  test_retrieval_query_gold.py
  test_retrieval_representation.py
  test_retrieval_sweep.py
  test_retrieval_metrics.py
  test_retrieval_report.py
```

Конвенції проєкту: `scripts/` на pythonpath → пакет імпортується як `retrieval.*`; async-тести без маркера (`asyncio_mode=auto`); unit-тести на фейках без БД/мережі; конвенційні коміти українською.

---

### Task 1: Пакет + хронологічне проріджування

**Files:**
- Create: `scripts/retrieval/__init__.py`
- Create: `scripts/retrieval/build_eval_corpus.py`
- Test: `tests/test_retrieval_thinning.py`

- [ ] **Step 1: Порожній `__init__.py`**

```bash
touch scripts/retrieval/__init__.py
```

- [ ] **Step 2: Написати падаючий тест**

```python
# tests/test_retrieval_thinning.py
from datetime import date

from prophet_checker.models.domain import (
    Prediction,
    PredictionStrength,
    PredictionValue,
)
from retrieval.build_eval_corpus import thin_chronologically


def _pred(pid: str, d: str, strength=PredictionStrength.LOW, value=PredictionValue.LOW):
    return Prediction(
        id=pid,
        document_id="doc",
        person_id="p",
        claim_text=f"claim {pid}",
        situation=f"situation {pid}",
        prediction_date=date.fromisoformat(d),
        prediction_strength=strength,
        prediction_value=value,
    )


def test_keeps_single_prediction():
    preds = [_pred("a", "2024-01-01")]
    assert [p.id for p in thin_chronologically(preds, min_gap_days=14)] == ["a"]


def test_drops_prediction_within_window_keeps_higher_score():
    # b на 3 дні пізніше a, у тому самому 14-денному вікні; b має вищий score → лишається b
    preds = [
        _pred("a", "2024-01-01", PredictionStrength.LOW, PredictionValue.LOW),
        _pred("b", "2024-01-04", PredictionStrength.HIGH, PredictionValue.HIGH),
    ]
    assert [p.id for p in thin_chronologically(preds, min_gap_days=14)] == ["b"]


def test_keeps_both_when_gap_exceeds_window():
    preds = [_pred("a", "2024-01-01"), _pred("b", "2024-02-01")]
    assert [p.id for p in thin_chronologically(preds, min_gap_days=14)] == ["a", "b"]


def test_next_window_anchored_on_kept_date():
    # a(01-01,low), b(01-10,high) → у вікні [01-01,01-15) лишається b(01-10);
    # наступне вікно стартує з b.date+14 = 01-24, тож c(01-20) відкидається, d(01-25) лишається
    preds = [
        _pred("a", "2024-01-01", PredictionStrength.LOW, PredictionValue.LOW),
        _pred("b", "2024-01-10", PredictionStrength.HIGH, PredictionValue.HIGH),
        _pred("c", "2024-01-20", PredictionStrength.LOW, PredictionValue.LOW),
        _pred("d", "2024-01-25", PredictionStrength.LOW, PredictionValue.LOW),
    ]
    assert [p.id for p in thin_chronologically(preds, min_gap_days=14)] == ["b", "d"]
```

- [ ] **Step 3: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_retrieval_thinning.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.build_eval_corpus'`

- [ ] **Step 4: Реалізувати мінімум**

```python
# scripts/retrieval/build_eval_corpus.py
from __future__ import annotations

from datetime import timedelta

from prophet_checker.models.domain import (
    Prediction,
    PredictionStrength,
    PredictionValue,
)

_RANK = {
    PredictionStrength.LOW: 0,
    PredictionStrength.MEDIUM: 1,
    PredictionStrength.HIGH: 2,
}
_VRANK = {
    PredictionValue.LOW: 0,
    PredictionValue.MEDIUM: 1,
    PredictionValue.HIGH: 2,
}


def _score(pred: Prediction) -> int:
    """Сумарний ранг strength+value (0..4). Вищий = вагоміший прогноз."""
    return _RANK[pred.prediction_strength] + _VRANK[pred.prediction_value]


def thin_chronologically(
    predictions: list[Prediction], min_gap_days: int = 14
) -> list[Prediction]:
    """Жадібне проріджування: у кожному вікні [anchor, anchor+gap) лишаємо прогноз із
    найвищим _score (тайбрейк: рання дата, далі id), наступне вікно стартує з kept.date+gap.
    Гарантує: дати лишених прогнозів ≥ min_gap_days одна від одної."""
    ordered = sorted(predictions, key=lambda p: (p.prediction_date, p.id))
    gap = timedelta(days=min_gap_days)
    kept: list[Prediction] = []
    i = 0
    n = len(ordered)
    while i < n:
        anchor = ordered[i].prediction_date
        window_end = anchor + gap
        group = []
        j = i
        while j < n and ordered[j].prediction_date < window_end:
            group.append(ordered[j])
            j += 1
        best = max(group, key=lambda p: (_score(p), -p.prediction_date.toordinal(), p.id))
        kept.append(best)
        next_start = best.prediction_date + gap
        while i < n and ordered[i].prediction_date < next_start:
            i += 1
    return kept
```

- [ ] **Step 5: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_retrieval_thinning.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Lint + commit**

```bash
.venv/bin/ruff check scripts/retrieval/ tests/test_retrieval_thinning.py
.venv/bin/ruff format scripts/retrieval/ tests/test_retrieval_thinning.py
git add scripts/retrieval/__init__.py scripts/retrieval/build_eval_corpus.py tests/test_retrieval_thinning.py
git commit -m "feat(retrieval): хронологічне проріджування корпусу для eval"
```

---

### Task 2: Завантаження корпусу + запис snapshot

**Files:**
- Modify: `scripts/retrieval/build_eval_corpus.py`
- Test: `tests/test_retrieval_corpus_io.py`

- [ ] **Step 1: Написати падаючий тест**

```python
# tests/test_retrieval_corpus_io.py
import json
from datetime import date

from prophet_checker.models.domain import (
    Prediction,
    PredictionStrength,
    PredictionValue,
)
from retrieval.build_eval_corpus import eligible, prediction_to_row, write_corpus


def _pred(pid, strength=PredictionStrength.HIGH, value=PredictionValue.HIGH, situation="s"):
    return Prediction(
        id=pid,
        document_id="doc",
        person_id="p",
        claim_text=f"claim {pid}",
        situation=situation,
        prediction_date=date(2024, 1, 1),
        topic="війна",
        prediction_strength=strength,
        prediction_value=value,
    )


def test_eligible_requires_strength_and_value():
    assert eligible(_pred("a")) is True
    p = _pred("b")
    p.prediction_strength = None
    assert eligible(p) is False


def test_prediction_to_row_shape():
    row = prediction_to_row(_pred("a"))
    assert row == {
        "id": "a",
        "claim_text": "claim a",
        "situation": "s",
        "topic": "війна",
        "prediction_date": "2024-01-01",
        "strength": "high",
        "value": "high",
    }


def test_write_corpus_roundtrip(tmp_path):
    out = tmp_path / "corpus.json"
    write_corpus([_pred("a"), _pred("b")], out)
    data = json.loads(out.read_text())
    assert [r["id"] for r in data] == ["a", "b"]
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_retrieval_corpus_io.py -v`
Expected: FAIL — `ImportError: cannot import name 'eligible'`

- [ ] **Step 3: Додати функції в `build_eval_corpus.py`**

```python
# scripts/retrieval/build_eval_corpus.py — додати імпорти зверху
import json
from pathlib import Path

# ... додати в кінець файлу:


def eligible(pred: Prediction) -> bool:
    """Придатний для корпусу: є strength і value (вихід верифікатора)."""
    return pred.prediction_strength is not None and pred.prediction_value is not None


def prediction_to_row(pred: Prediction) -> dict:
    return {
        "id": pred.id,
        "claim_text": pred.claim_text,
        "situation": pred.situation,
        "topic": pred.topic,
        "prediction_date": pred.prediction_date.isoformat(),
        "strength": pred.prediction_strength.value,
        "value": pred.prediction_value.value,
    }


def write_corpus(predictions: list[Prediction], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [prediction_to_row(p) for p in predictions]
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_retrieval_corpus_io.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Додати `main()` (read DB → filter → thin → write)**

```python
# scripts/retrieval/build_eval_corpus.py — додати в кінець
import argparse
import asyncio
from contextlib import AsyncExitStack

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from prophet_checker.config import Settings
from prophet_checker.storage.postgres import PostgresPredictionRepository

CORPUS_PATH = Path("scripts/data/retrieval_eval_corpus.json")


async def build(person_id: str, min_gap_days: int, out_path: Path) -> int:
    settings = Settings()
    async with AsyncExitStack() as stack:
        engine = create_async_engine(settings.database_url, echo=False)
        stack.push_async_callback(engine.dispose)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        repo = PostgresPredictionRepository(session_factory)
        predictions = await repo.get_by_person(person_id)
    usable = [p for p in predictions if eligible(p)]
    corpus = thin_chronologically(usable, min_gap_days=min_gap_days)
    write_corpus(corpus, out_path)
    return len(corpus)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--person-id", required=True)
    parser.add_argument("--min-gap-days", type=int, default=14)
    parser.add_argument("--out", type=Path, default=CORPUS_PATH)
    args = parser.parse_args()
    count = asyncio.run(build(args.person_id, args.min_gap_days, args.out))
    print(f"eval corpus: {count} predictions → {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Lint + commit**

```bash
.venv/bin/ruff check scripts/retrieval/build_eval_corpus.py tests/test_retrieval_corpus_io.py
.venv/bin/ruff format scripts/retrieval/build_eval_corpus.py tests/test_retrieval_corpus_io.py
git add scripts/retrieval/build_eval_corpus.py tests/test_retrieval_corpus_io.py
git commit -m "feat(retrieval): завантаження прод-прогнозів і запис snapshot корпусу"
```

---

### Task 3: Стратифікований відбір цілей

**Files:**
- Create: `scripts/retrieval/build_query_gold.py`
- Test: `tests/test_retrieval_sampling.py`

- [ ] **Step 1: Написати падаючий тест**

```python
# tests/test_retrieval_sampling.py
from retrieval.build_query_gold import sample_targets


def _row(rid, topic, dt):
    return {"id": rid, "topic": topic, "prediction_date": dt, "claim_text": "c", "situation": "s"}


def test_sample_is_deterministic_for_seed():
    corpus = [_row(str(i), "війна" if i % 2 else "економіка", f"2024-0{i % 9 + 1}-01") for i in range(20)]
    a = [r["id"] for r in sample_targets(corpus, n=6, seed=42)]
    b = [r["id"] for r in sample_targets(corpus, n=6, seed=42)]
    assert a == b


def test_sample_size_capped_at_corpus():
    corpus = [_row("a", "війна", "2024-01-01"), _row("b", "війна", "2024-02-01")]
    assert len(sample_targets(corpus, n=10, seed=1)) == 2


def test_sample_spreads_across_topics():
    corpus = [_row(f"w{i}", "війна", "2024-01-01") for i in range(10)]
    corpus += [_row(f"e{i}", "економіка", "2024-01-01") for i in range(10)]
    ids = [r["id"] for r in sample_targets(corpus, n=4, seed=7)]
    assert any(i.startswith("w") for i in ids) and any(i.startswith("e") for i in ids)
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_retrieval_sampling.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.build_query_gold'`

- [ ] **Step 3: Реалізувати відбір**

```python
# scripts/retrieval/build_query_gold.py
from __future__ import annotations

import random
from collections import defaultdict
from itertools import cycle


def _cell(row: dict) -> tuple[str, str]:
    """Стратифікаційна клітинка: (topic, рік)."""
    year = str(row["prediction_date"])[:4]
    return (row.get("topic", ""), year)


def sample_targets(corpus: list[dict], n: int, seed: int) -> list[dict]:
    """Round-robin по клітинках (topic, рік) для рівномірного покриття; детерміновано по seed."""
    rng = random.Random(seed)
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in corpus:
        cells[_cell(row)].append(row)
    for key in cells:
        cells[key].sort(key=lambda r: r["id"])
        rng.shuffle(cells[key])
    keys = sorted(cells.keys())
    picked: list[dict] = []
    seen: set[str] = set()
    for key in cycle(keys):
        if len(picked) >= n or len(seen) >= len(corpus):
            break
        bucket = cells[key]
        if bucket:
            row = bucket.pop()
            picked.append(row)
            seen.add(row["id"])
    return picked[:n]
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_retrieval_sampling.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check scripts/retrieval/build_query_gold.py tests/test_retrieval_sampling.py
.venv/bin/ruff format scripts/retrieval/build_query_gold.py tests/test_retrieval_sampling.py
git add scripts/retrieval/build_query_gold.py tests/test_retrieval_sampling.py
git commit -m "feat(retrieval): стратифікований відбір цілей для gold"
```

---

### Task 4: Промпт генерації запитів + збірка записів

**Files:**
- Modify: `scripts/retrieval/build_query_gold.py`
- Test: `tests/test_retrieval_query_gold.py`

- [ ] **Step 1: Написати падаючий тест**

```python
# tests/test_retrieval_query_gold.py
from retrieval.build_query_gold import build_query_prompt, generate_queries


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append(prompt)
        return "  згенерований запит  "


def test_prompt_uses_claim_text_for_content():
    row = {"id": "a", "claim_text": "Авдіївка впаде", "situation": "взимку 2024"}
    p = build_query_prompt(row, "claim_text")
    assert "Авдіївка впаде" in p and "не копіюй" in p.lower()


def test_prompt_uses_situation_for_context():
    row = {"id": "a", "claim_text": "Авдіївка впаде", "situation": "взимку 2024"}
    p = build_query_prompt(row, "situation")
    assert "взимку 2024" in p


async def test_generate_two_queries_when_situation_present():
    row = {"id": "a", "claim_text": "c", "situation": "s"}
    recs = await generate_queries(row, FakeLLM())
    assert [r["source_field"] for r in recs] == ["claim_text", "situation"]
    assert all(r["target_id"] == "a" for r in recs)
    assert recs[0]["query"] == "згенерований запит"  # обрізані пробіли


async def test_generate_skips_context_when_no_situation():
    row = {"id": "a", "claim_text": "c", "situation": ""}
    recs = await generate_queries(row, FakeLLM())
    assert [r["source_field"] for r in recs] == ["claim_text"]
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_retrieval_query_gold.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_query_prompt'`

- [ ] **Step 3: Реалізувати промпт і генерацію**

```python
# scripts/retrieval/build_query_gold.py — додати

_FIELD_LABEL = {
    "claim_text": "ЗМІСТ прогнозу (що саме спрогнозовано)",
    "situation": "ОБСТАВИНИ, за яких зроблено прогноз (період, подія)",
}


def build_query_prompt(row: dict, source_field: str) -> str:
    source_text = row["claim_text"] if source_field == "claim_text" else row["situation"]
    return (
        "Ти формуєш пошуковий запит, який пересічний користувач написав би, щоб знайти прогноз.\n"
        f"Орієнтуйся на {_FIELD_LABEL[source_field]}.\n\n"
        f"Текст-джерело:\n«{source_text}»\n\n"
        "Правила:\n"
        "- одне коротке питання природною українською;\n"
        "- НЕ копіюй характерні слова, числа, назви з джерела дослівно — узагальнюй;\n"
        "- пиши як жива людина, не як цитата.\n\n"
        "Поверни ЛИШЕ текст запиту, без лапок і пояснень."
    )


async def generate_queries(row: dict, llm) -> list[dict]:
    fields = ["claim_text"]
    if (row.get("situation") or "").strip():
        fields.append("situation")
    records = []
    for field in fields:
        query = (await llm.complete(build_query_prompt(row, field))).strip()
        records.append({"query": query, "target_id": row["id"], "source_field": field})
    return records
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_retrieval_query_gold.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check scripts/retrieval/build_query_gold.py tests/test_retrieval_query_gold.py
.venv/bin/ruff format scripts/retrieval/build_query_gold.py tests/test_retrieval_query_gold.py
git add scripts/retrieval/build_query_gold.py tests/test_retrieval_query_gold.py
git commit -m "feat(retrieval): промпт і генерація content/context запитів"
```

---

### Task 5: `build_query_gold` main + шаблон ручного зрізу

**Files:**
- Modify: `scripts/retrieval/build_query_gold.py`
- Test: `tests/test_retrieval_query_gold.py` (доповнення)

- [ ] **Step 1: Дописати падаючий тест**

```python
# tests/test_retrieval_query_gold.py — додати
import json

from retrieval.build_query_gold import ensure_manual_stub, run_gold


async def test_run_gold_writes_records(tmp_path):
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps([
        {"id": "a", "claim_text": "c", "situation": "s", "topic": "війна", "prediction_date": "2024-01-01"},
    ]))
    out = tmp_path / "gold.json"
    await run_gold(corpus, out, n=1, seed=1, llm=FakeLLM())
    recs = json.loads(out.read_text())
    assert {r["source_field"] for r in recs} == {"claim_text", "situation"}


def test_ensure_manual_stub_creates_empty_list(tmp_path):
    path = tmp_path / "manual.json"
    ensure_manual_stub(path)
    assert json.loads(path.read_text()) == []
    path.write_text('[{"query": "x", "target_id": "a"}]')
    ensure_manual_stub(path)  # не перетирає наявний
    assert len(json.loads(path.read_text())) == 1
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_retrieval_query_gold.py::test_run_gold_writes_records -v`
Expected: FAIL — `ImportError: cannot import name 'run_gold'`

- [ ] **Step 3: Реалізувати main + stub**

```python
# scripts/retrieval/build_query_gold.py — додати
import argparse
import asyncio
import json
from pathlib import Path

from prophet_checker.config import Settings
from prophet_checker.llm import LLMClient

CORPUS_PATH = Path("scripts/data/retrieval_eval_corpus.json")
GOLD_PATH = Path("scripts/data/retrieval_query_gold.json")
MANUAL_PATH = Path("scripts/data/retrieval_query_gold_manual.json")


def ensure_manual_stub(path: Path) -> None:
    if not path.exists():
        path.write_text("[]")


async def run_gold(corpus_path: Path, out_path: Path, n: int, seed: int, llm) -> int:
    corpus = json.loads(corpus_path.read_text())
    targets = sample_targets(corpus, n=n, seed=seed)
    records: list[dict] = []
    for row in targets:
        records.extend(await generate_queries(row, llm))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=80)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--out", type=Path, default=GOLD_PATH)
    args = parser.parse_args()
    settings = Settings()
    llm = LLMClient(
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        api_key=settings.gemini_api_key,
        temperature=0,
    )
    count = asyncio.run(run_gold(args.corpus, args.out, args.n, args.seed, llm))
    ensure_manual_stub(MANUAL_PATH)
    print(f"gold: {count} queries → {args.out}; ручний зріз: {MANUAL_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_retrieval_query_gold.py -v`
Expected: PASS (всі)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check scripts/retrieval/build_query_gold.py tests/test_retrieval_query_gold.py
.venv/bin/ruff format scripts/retrieval/build_query_gold.py tests/test_retrieval_query_gold.py
git add scripts/retrieval/build_query_gold.py tests/test_retrieval_query_gold.py
git commit -m "feat(retrieval): main генерації gold + шаблон ручного зрізу"
```

---

### Task 6: Адаптер eval-сховища (DDL + Protocol + Postgres)

**Files:**
- Create: `scripts/retrieval/eval_store.py`
- Test: інтеграційно (smoke, Task 10) — unit тести використовують фейк нижче.

- [ ] **Step 1: Реалізувати сховище**

```python
# scripts/retrieval/eval_store.py
from __future__ import annotations

from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

EVAL_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS retrieval_eval_emb (
    prediction_id TEXT NOT NULL,
    config        TEXT NOT NULL,
    embedding     vector NOT NULL
)
"""


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


class EvalEmbStore(Protocol):
    async def ensure_table(self) -> None: ...
    async def recreate(self, config: str) -> None: ...
    async def add(self, config: str, prediction_id: str, embedding: list[float]) -> None: ...
    async def search(self, config: str, query: list[float], limit: int) -> list[str]: ...


class PostgresEvalEmbStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def ensure_table(self) -> None:
        async with self._sf() as s:
            await s.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await s.execute(text(EVAL_TABLE_DDL))
            await s.commit()

    async def recreate(self, config: str) -> None:
        async with self._sf() as s:
            await s.execute(
                text("DELETE FROM retrieval_eval_emb WHERE config = :c"), {"c": config}
            )
            await s.commit()

    async def add(self, config: str, prediction_id: str, embedding: list[float]) -> None:
        async with self._sf() as s:
            await s.execute(
                text(
                    "INSERT INTO retrieval_eval_emb (prediction_id, config, embedding) "
                    "VALUES (:pid, :c, (:emb)::vector)"
                ),
                {"pid": prediction_id, "c": config, "emb": _vec_literal(embedding)},
            )
            await s.commit()

    async def search(self, config: str, query: list[float], limit: int) -> list[str]:
        async with self._sf() as s:
            result = await s.execute(
                text(
                    "SELECT prediction_id FROM retrieval_eval_emb WHERE config = :c "
                    "ORDER BY embedding <=> (:q)::vector LIMIT :k"
                ),
                {"c": config, "q": _vec_literal(query), "k": limit},
            )
            return [r[0] for r in result.all()]
```

- [ ] **Step 2: Lint + commit**

```bash
.venv/bin/ruff check scripts/retrieval/eval_store.py
.venv/bin/ruff format scripts/retrieval/eval_store.py
git add scripts/retrieval/eval_store.py
git commit -m "feat(retrieval): адаптер eval-сховища (безрозмірна vector-таблиця)"
```

---

### Task 7: Текст репрезентації + sweep-ембединг

**Files:**
- Create: `scripts/retrieval/embed_corpus.py`
- Test: `tests/test_retrieval_representation.py`, `tests/test_retrieval_sweep.py`

- [ ] **Step 1: Тест на текст репрезентації**

```python
# tests/test_retrieval_representation.py
from retrieval.embed_corpus import build_representation_text


def test_claim_text():
    row = {"claim_text": "C", "situation": "S"}
    assert build_representation_text(row, "claim_text") == "C"


def test_situation_skips_when_empty():
    assert build_representation_text({"claim_text": "C", "situation": ""}, "situation") is None


def test_claim_situation_concat():
    row = {"claim_text": "C", "situation": "S"}
    assert build_representation_text(row, "claim_situation") == "C\nS"


def test_claim_situation_falls_back_to_claim_when_no_situation():
    assert build_representation_text({"claim_text": "C", "situation": ""}, "claim_situation") == "C"
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_retrieval_representation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.embed_corpus'`

- [ ] **Step 3: Реалізувати текст репрезентації**

```python
# scripts/retrieval/embed_corpus.py
from __future__ import annotations

REPRESENTATIONS = ("claim_text", "situation", "claim_situation")


def build_representation_text(row: dict, kind: str) -> str | None:
    """Текст для ембедингу. None → прогноз пропускається в цій репрезентації."""
    claim = row["claim_text"]
    situation = (row.get("situation") or "").strip()
    if kind == "claim_text":
        return claim
    if kind == "situation":
        return situation or None
    if kind == "claim_situation":
        return f"{claim}\n{situation}" if situation else claim
    raise ValueError(f"unknown representation: {kind}")
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_retrieval_representation.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Тест на sweep (фейкові ембедер і сховище)**

```python
# tests/test_retrieval_sweep.py
from retrieval.embed_corpus import run_sweep


class FakeEmbedder:
    def __init__(self, model):
        self.model = model

    async def embed(self, text: str) -> list[float]:
        return [float(len(text)), float(self.model == "m2")]


class FakeStore:
    def __init__(self):
        self.rows = []
        self.recreated = []
        self.ensured = False

    async def ensure_table(self):
        self.ensured = True

    async def recreate(self, config):
        self.recreated.append(config)

    async def add(self, config, prediction_id, embedding):
        self.rows.append((config, prediction_id, embedding))

    async def search(self, config, query, limit):
        return []


async def test_sweep_populates_per_config_and_skips_empty_situation():
    corpus = [
        {"id": "a", "claim_text": "AA", "situation": "sit"},
        {"id": "b", "claim_text": "BB", "situation": ""},
    ]
    store = FakeStore()
    await run_sweep(
        corpus,
        configs=[("m1", "claim_text"), ("m1", "situation")],
        embedder_factory=FakeEmbedder,
        store=store,
    )
    assert store.ensured is True
    # claim_text: обидва прогнози; situation: лише "a" (b має порожню situation)
    ct = [r for r in store.rows if r[0] == "m1__claim_text"]
    sit = [r for r in store.rows if r[0] == "m1__situation"]
    assert {r[1] for r in ct} == {"a", "b"}
    assert {r[1] for r in sit} == {"a"}
    assert "m1__claim_text" in store.recreated and "m1__situation" in store.recreated
```

- [ ] **Step 6: Реалізувати `run_sweep`**

```python
# scripts/retrieval/embed_corpus.py — додати


def config_name(model: str, kind: str) -> str:
    return f"{model}__{kind}"


async def run_sweep(corpus: list[dict], configs, embedder_factory, store) -> None:
    """configs: список (model, representation_kind). embedder_factory(model) → обʼєкт з .embed."""
    await store.ensure_table()
    for model, kind in configs:
        name = config_name(model, kind)
        await store.recreate(name)
        embedder = embedder_factory(model)
        for row in corpus:
            text_ = build_representation_text(row, kind)
            if text_ is None:
                continue
            vector = await embedder.embed(text_)
            await store.add(name, row["id"], vector)
```

- [ ] **Step 7: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_retrieval_sweep.py tests/test_retrieval_representation.py -v`
Expected: PASS

- [ ] **Step 8: Додати `main()`**

```python
# scripts/retrieval/embed_corpus.py — додати
import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from prophet_checker.config import Settings
from prophet_checker.llm import EmbeddingClient
from retrieval.eval_store import PostgresEvalEmbStore

CORPUS_PATH = Path("scripts/data/retrieval_eval_corpus.json")

# Кандидати фіналізуються screening'ом по MMTEB UK/RU; baseline лишається першим.
MODELS = ["text-embedding-3-small"]


async def run(corpus_path: Path, models: list[str]) -> None:
    settings = Settings()
    corpus = json.loads(corpus_path.read_text())
    configs = [(m, k) for m in от  for k in REPRESENTATIONS]

    def factory(model: str):
        return EmbeddingClient(model=model, api_key=settings.openai_api_key)

    async with AsyncExitStack() as stack:
        engine = create_async_engine(settings.database_url, echo=False)
        stack.push_async_callback(engine.dispose)
        store = PostgresEvalEmbStore(async_sessionmaker(engine, expire_on_commit=False))
        await run_sweep(corpus, configs, factory, store)
    print(f"sweep done: {len(configs)} configs × {len(corpus)} predictions")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--models", nargs="+", default=MODELS)
    args = parser.parse_args()
    asyncio.run(run(args.corpus, args.models))


if __name__ == "__main__":
    main()
```

- [ ] **Step 9: Lint + commit**

```bash
.venv/bin/ruff check scripts/retrieval/embed_corpus.py tests/test_retrieval_representation.py tests/test_retrieval_sweep.py
.venv/bin/ruff format scripts/retrieval/embed_corpus.py tests/test_retrieval_representation.py tests/test_retrieval_sweep.py
git add scripts/retrieval/embed_corpus.py tests/test_retrieval_representation.py tests/test_retrieval_sweep.py
git commit -m "feat(retrieval): sweep-ембединг корпусу по комбінаціях"
```

---

### Task 8: Метрики recall@k / MRR + агрегація

**Files:**
- Create: `scripts/retrieval/retrieval_eval.py`
- Test: `tests/test_retrieval_metrics.py`

- [ ] **Step 1: Написати падаючий тест**

```python
# tests/test_retrieval_metrics.py
from retrieval.retrieval_eval import aggregate_metrics, recall_at_k, reciprocal_rank


def test_recall_at_k_hit_and_miss():
    assert recall_at_k(["x", "a", "y"], "a", 2) == 1.0   # на позиції 2 (індекс 1) → у топ-2
    assert recall_at_k(["x", "y", "a"], "a", 2) == 0.0   # на позиції 3 → не в топ-2


def test_reciprocal_rank():
    assert reciprocal_rank(["a", "b"], "a") == 1.0
    assert reciprocal_rank(["b", "a"], "a") == 0.5
    assert reciprocal_rank(["b", "c"], "a") == 0.0


def test_aggregate_splits_by_source_field():
    results = [
        {"source_field": "claim_text", "ranked": ["a"], "target_id": "a"},   # hit@1
        {"source_field": "situation", "ranked": ["x", "b"], "target_id": "b"},  # hit@5, miss@1
    ]
    agg = aggregate_metrics(results, ks=[1, 5])
    assert agg["overall"]["recall@1"] == 0.5
    assert agg["claim_text"]["recall@1"] == 1.0
    assert agg["situation"]["recall@1"] == 0.0
    assert agg["situation"]["recall@5"] == 1.0
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_retrieval_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.retrieval_eval'`

- [ ] **Step 3: Реалізувати метрики**

```python
# scripts/retrieval/retrieval_eval.py
from __future__ import annotations


def recall_at_k(ranked: list[str], target_id: str, k: int) -> float:
    return 1.0 if target_id in ranked[:k] else 0.0


def reciprocal_rank(ranked: list[str], target_id: str) -> float:
    if target_id in ranked:
        return 1.0 / (ranked.index(target_id) + 1)
    return 0.0


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def aggregate_metrics(results: list[dict], ks: list[int]) -> dict:
    """results: [{source_field, ranked, target_id}]. Повертає метрики overall + по source_field."""
    groups: dict[str, list[dict]] = {"overall": list(results)}
    for r in results:
        groups.setdefault(r["source_field"], []).append(r)
    out: dict[str, dict] = {}
    for name, rows in groups.items():
        metrics = {f"recall@{k}": _mean([recall_at_k(r["ranked"], r["target_id"], k) for r in rows]) for k in ks}
        metrics["mrr"] = _mean([reciprocal_rank(r["ranked"], r["target_id"]) for r in rows])
        metrics["n"] = len(rows)
        out[name] = metrics
    return out
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_retrieval_metrics.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check scripts/retrieval/retrieval_eval.py tests/test_retrieval_metrics.py
.venv/bin/ruff format scripts/retrieval/retrieval_eval.py tests/test_retrieval_metrics.py
git add scripts/retrieval/retrieval_eval.py tests/test_retrieval_metrics.py
git commit -m "feat(retrieval): метрики recall@k/MRR з розбивкою по source_field"
```

---

### Task 9: Звіт + `run_eval` + main

**Files:**
- Modify: `scripts/retrieval/retrieval_eval.py`
- Test: `tests/test_retrieval_report.py`

- [ ] **Step 1: Написати падаючий тест**

```python
# tests/test_retrieval_report.py
import json

from retrieval.retrieval_eval import render_report, run_eval


def test_render_report_has_row_per_config():
    per_config = {
        "m1__claim_text": {"overall": {"recall@1": 0.5, "recall@10": 0.8, "mrr": 0.6, "n": 10}},
        "m1__situation": {"overall": {"recall@1": 0.3, "recall@10": 0.7, "mrr": 0.4, "n": 10}},
    }
    md = render_report(per_config, ks=[1, 10])
    assert "m1__claim_text" in md and "m1__situation" in md
    assert "recall@10" in md and "0.8" in md


class FakeEmbedder:
    def __init__(self, model):
        pass

    async def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeStore:
    async def ensure_table(self):
        pass

    async def search(self, config, query, limit):
        return ["a", "b"]  # завжди повертає "a" першим


async def test_run_eval_produces_metrics_per_config(tmp_path):
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps([{"query": "q", "target_id": "a", "source_field": "claim_text"}]))
    per_config = await run_eval(
        gold_path=gold,
        configs=[("m1", "claim_text")],
        embedder_factory=FakeEmbedder,
        store=FakeStore(),
        ks=[1],
    )
    assert per_config["m1__claim_text"]["overall"]["recall@1"] == 1.0
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_retrieval_report.py -v`
Expected: FAIL — `ImportError: cannot import name 'render_report'`

- [ ] **Step 3: Реалізувати звіт, run_eval, main**

```python
# scripts/retrieval/retrieval_eval.py — додати
import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from prophet_checker.config import Settings
from prophet_checker.llm import EmbeddingClient
from retrieval.embed_corpus import REPRESENTATIONS, config_name
from retrieval.eval_store import PostgresEvalEmbStore

GOLD_PATH = Path("scripts/data/retrieval_query_gold.json")
REPORT_PATH = Path("scripts/outputs/retrieval_eval/retrieval_eval_report.md")


def render_report(per_config: dict, ks: list[int]) -> str:
    cols = [f"recall@{k}" for k in ks] + ["mrr", "n"]
    header = "| config | scope | " + " | ".join(cols) + " |"
    sep = "|" + "---|" * (len(cols) + 2)
    lines = ["# Retrieval eval report", "", header, sep]
    for name in sorted(per_config):
        for scope in sorted(per_config[name]):
            m = per_config[name][scope]
            cells = [f"{m.get(c, 0):.3f}" if c != "n" else str(m.get("n", 0)) for c in cols]
            lines.append(f"| {name} | {scope} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


async def run_eval(gold_path: Path, configs, embedder_factory, store, ks: list[int]) -> dict:
    gold = json.loads(gold_path.read_text())
    await store.ensure_table()
    limit = max(ks)
    per_config: dict[str, dict] = {}
    for model, kind in configs:
        name = config_name(model, kind)
        embedder = embedder_factory(model)
        results = []
        for item in gold:
            qvec = await embedder.embed(item["query"])
            ranked = await store.search(name, qvec, limit)
            results.append(
                {"source_field": item["source_field"], "ranked": ranked, "target_id": item["target_id"]}
            )
        per_config[name] = aggregate_metrics(results, ks)
    return per_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=GOLD_PATH)
    parser.add_argument("--models", nargs="+", default=["text-embedding-3-small"])
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 5, 10, 20])
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    settings = Settings()
    configs = [(m, k) for m in args.models for k in REPRESENTATIONS]

    def factory(model: str):
        return EmbeddingClient(model=model, api_key=settings.openai_api_key)

    async def _run():
        async with AsyncExitStack() as stack:
            engine = create_async_engine(settings.database_url, echo=False)
            stack.push_async_callback(engine.dispose)
            store = PostgresEvalEmbStore(async_sessionmaker(engine, expire_on_commit=False))
            return await run_eval(args.gold, configs, factory, store, args.ks)

    per_config = asyncio.run(_run())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(per_config, args.ks))
    print(f"report → {args.report}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_retrieval_report.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Прогнати весь retrieval-набір тестів**

Run: `.venv/bin/python -m pytest tests/test_retrieval_*.py -v`
Expected: PASS (усі)

- [ ] **Step 6: Lint + commit**

```bash
.venv/bin/ruff check scripts/retrieval/retrieval_eval.py tests/test_retrieval_report.py
.venv/bin/ruff format scripts/retrieval/retrieval_eval.py tests/test_retrieval_report.py
git add scripts/retrieval/retrieval_eval.py tests/test_retrieval_report.py
git commit -m "feat(retrieval): cosine-пошук, звіт і CLI eval"
```

---

### Task 10: Інтеграційний smoke (real Postgres + LLM, опційно)

**Files:**
- Create: `scripts/retrieval/integration_smoke.py`

- [ ] **Step 1: Реалізувати smoke-скрипт**

```python
# scripts/retrieval/integration_smoke.py
"""Малий наскрізний прогін на реальних Postgres+LLM (як scripts/ingestion/integration_smoke.py).
Передумова: docker compose up -d; alembic upgrade head; у БД є верифіковані прогнози.

Usage:
    .venv/bin/python scripts/retrieval/integration_smoke.py --person-id <id> --n 3
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from retrieval.build_eval_corpus import build
from retrieval.build_query_gold import run_gold
from retrieval.embed_corpus import run as run_embed
from retrieval.retrieval_eval import REPORT_PATH


async def smoke(person_id: str, n: int) -> None:
    from prophet_checker.config import Settings
    from prophet_checker.llm import LLMClient

    corpus_path = Path("scripts/data/_smoke_corpus.json")
    gold_path = Path("scripts/data/_smoke_gold.json")

    count = await build(person_id, min_gap_days=14, out_path=corpus_path)
    print(f"[1/3] corpus: {count}")

    settings = Settings()
    llm = LLMClient(
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        api_key=settings.gemini_api_key,
        temperature=0,
    )
    g = await run_gold(corpus_path, gold_path, n=n, seed=1, llm=llm)
    print(f"[2/3] gold: {g}")

    await run_embed(corpus_path, ["text-embedding-3-small"])
    print(f"[3/3] embed done → перевір {REPORT_PATH} після retrieval_eval.main")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--person-id", required=True)
    parser.add_argument("--n", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(smoke(args.person_id, args.n))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: (Вручну, опційно) прогнати smoke**

Run:
```bash
docker compose up -d
.venv/bin/alembic upgrade head
.venv/bin/python scripts/retrieval/integration_smoke.py --person-id <arestovich_id> --n 3
.venv/bin/python scripts/retrieval/retrieval_eval.py --gold scripts/data/_smoke_gold.json
```
Expected: друкує `[1/3]/[2/3]/[3/3]` і генерує markdown-звіт без помилок.

- [ ] **Step 3: Commit**

```bash
.venv/bin/ruff check scripts/retrieval/integration_smoke.py
.venv/bin/ruff format scripts/retrieval/integration_smoke.py
git add scripts/retrieval/integration_smoke.py
git commit -m "feat(retrieval): наскрізний integration smoke на реальних сервісах"
```

---

## Запуск (порядок, після імплементації)

```bash
# Передумова: екстракція + верифікація по історії, щоб у БД були прогнози зі strength/value.
# Запуск — файлом (скрипти самі кладуть src/ + scripts/ у sys.path і вантажать .env).
.venv/bin/python scripts/retrieval/build_eval_corpus.py --person-id <id> --min-gap-days 14
.venv/bin/python scripts/retrieval/build_query_gold.py --n 80 --seed 13
# (вручну) заповнити scripts/data/retrieval_query_gold_manual.json ~20 запитами
.venv/bin/python scripts/retrieval/embed_corpus.py --models text-embedding-3-small <candidate-2> <candidate-3>
.venv/bin/python scripts/retrieval/retrieval_eval.py --models text-embedding-3-small <candidate-2> <candidate-3>
# → scripts/outputs/retrieval_eval/retrieval_eval_report.md
```

## Follow-ups (поза цим планом)

- Screening моделей по MMTEB UK/RU → фіналізувати список `--models`.
- Ручний валідаційний зріз: окремий прогін метрик на `retrieval_query_gold_manual.json` і звірка порядку.
- За фактом переможця: прокинути репрезентацію в прод-інжест (`ingestion/orchestrator.py`) і мігрувати `predictions.embedding` під dim переможця.
