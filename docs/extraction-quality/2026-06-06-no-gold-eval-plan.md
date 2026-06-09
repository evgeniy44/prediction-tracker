# Extraction-quality eval без gold — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development або superpowers:executing-plans. Кроки — checkbox (`- [ ]`).

**Goal:** Зробити gold опціональним у `extraction_quality_eval.py` — прапорець `--no-gold` дає judge-only метрики, gold-залежні поля стають `null`.

**Architecture:** gold протікає `_main_async → run_stage3_aggregate → aggregate_metrics`. Робимо кожну ланку gold-опціональною; judge-only обчислення не чіпаємо. With-gold поведінка ідентична.

**Tech Stack:** Python 3.12, pytest (`asyncio_mode=auto`).

**Обмеження:** NO нових docstrings/inline comments (файл — старий eval-скрипт із наявними docstrings; їх не чіпаємо, нових не додаємо). `.venv/bin/python`. cwd `/Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker` (префікс `cd`). Українські коміти; кінець тіла: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`. Наявні 207 → 210.

---

### Task 1: `aggregate_metrics` no-gold + null-поля (TDD)

**Files:**
- Modify: `scripts/extraction/extraction_quality_eval.py`
- Test: `tests/test_extraction_quality_eval.py`

- [ ] **Step 1: додати падючі тести (в кінець tests/test_extraction_quality_eval.py)**

```python
def test_aggregate_metrics_no_gold_nulls_gold_fields():
    from extraction.extraction_quality_eval import aggregate_metrics
    judgements = {
        "model_x": {
            "post_1": {
                "per_claim": [{"verdict": "exact_match"}, {"verdict": "hallucination"}],
                "missed_predictions": [{"text_excerpt": "X", "why_valid": "..."}],
            },
        }
    }
    m = aggregate_metrics(judgements=judgements, gold_labels=None)["per_model"]["model_x"]
    assert m["missed_rate"] is None
    assert m["gold_agreement"] is None
    assert m["total_claims"] == 2
    assert m["avg_quality_score"] == pytest.approx(1.5, abs=1e-6)
    assert m["hallucination_rate"] == pytest.approx(0.5, abs=1e-6)
    assert m["missed_predictions_count"] == 1


def test_aggregate_metrics_empty_gold_treated_as_no_gold():
    from extraction.extraction_quality_eval import aggregate_metrics
    judgements = {"model_x": {"p": {"per_claim": [{"verdict": "exact_match"}], "missed_predictions": []}}}
    m = aggregate_metrics(judgements=judgements, gold_labels=[])["per_model"]["model_x"]
    assert m["missed_rate"] is None
    assert m["gold_agreement"] is None
    assert m["total_claims"] == 1
```

- [ ] **Step 2: прогнати — мають впасти**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_extraction_quality_eval.py -q -k no_gold`
Expected: FAIL (`missed_rate`==0.0, не None; та/або TypeError якщо gold_labels=None ще не дозволено).

- [ ] **Step 3: оновити сигнатуру `aggregate_metrics`**

Замінити:
```python
def aggregate_metrics(
    judgements: dict, gold_labels: list[dict]
) -> dict:
```
на:
```python
def aggregate_metrics(
    judgements: dict, gold_labels: list[dict] | None = None
) -> dict:
```

- [ ] **Step 4: gold_index під no_gold**

Замінити рядок:
```python
    gold_index = {g["id"]: g["has_prediction"] for g in gold_labels}
```
на:
```python
    no_gold = not gold_labels
    gold_index = {} if no_gold else {g["id"]: g["has_prediction"] for g in gold_labels}
```

- [ ] **Step 5: null gold-полів у per_model**

Замінити блок:
```python
            "missed_rate": missed_rate,
            "gold_agreement": {
                "gold_YES_with_valid_extraction": gold_yes_with_valid,
                "gold_YES_no_valid_extraction": gold_yes_no_valid,
                "gold_NO_with_extractions_labeled_valid": gold_no_with_valid,
                "gold_NO_without_valid_extractions": gold_no_no_valid,
            },
```
на:
```python
            "missed_rate": None if no_gold else missed_rate,
            "gold_agreement": None if no_gold else {
                "gold_YES_with_valid_extraction": gold_yes_with_valid,
                "gold_YES_no_valid_extraction": gold_yes_no_valid,
                "gold_NO_with_extractions_labeled_valid": gold_no_with_valid,
                "gold_NO_without_valid_extractions": gold_no_no_valid,
            },
```

- [ ] **Step 6: прогнати — нові + наявні зелені**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/ruff check scripts/extraction/extraction_quality_eval.py && .venv/bin/python -m pytest tests/test_extraction_quality_eval.py -q`
Expected: ruff clean; `32 passed` (30 наявних + 2 нових).

- [ ] **Step 7: commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git add scripts/extraction/extraction_quality_eval.py tests/test_extraction_quality_eval.py && git commit -m "$(printf 'feat(extraction): aggregate_metrics без gold → null gold-полів\n\ngold_labels опціональний; no_gold (None або []) → missed_rate/gold_agreement\n= null, judge-only метрики незмінні. +2 тести.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: `run_stage3_aggregate` — опціональний gold-шлях

**Files:**
- Modify: `scripts/extraction/extraction_quality_eval.py`

- [ ] **Step 1: сигнатура — gold_labels_path опціональний**

Замінити:
```python
    judgements_path: Path,
    gold_labels_path: Path,
    output_path: Path,
) -> dict:
```
на:
```python
    judgements_path: Path,
    gold_labels_path: Path | None = None,
    output_path: Path = None,
) -> dict:
```
(Зверни увагу: `output_path` стоїть після опціонального — щоб не зламати позиційні виклики, лиши порядок як у спеці; якщо ruff/виклики вимагають — лиши `output_path: Path` без дефолта і просто додай `| None = None` лише до `gold_labels_path`. Перевір наявні виклики `run_stage3_aggregate(` — вони keyword-аргументами, тож безпечно.)

ФАКТИЧНА мінімальна заміна (keyword-виклики → дефолт не потрібен на output_path):
```python
    judgements_path: Path,
    gold_labels_path: Path | None = None,
    output_path: Path,
) -> dict:
```
Якщо Python лається на non-default після default — тоді прибери `= None` (лиши `gold_labels_path: Path | None`) і покладайся на явну передачу `None` з `_main_async`:
```python
    judgements_path: Path,
    gold_labels_path: Path | None,
    output_path: Path,
) -> dict:
```
**Використай останній варіант** (без дефолта, але `| None`) — він безпечний і виклики передають аргумент явно.

- [ ] **Step 2: читання gold під None**

Замінити:
```python
    gold_labels = json.loads(gold_labels_path.read_text(encoding="utf-8"))
```
на:
```python
    gold_labels = None if gold_labels_path is None else json.loads(gold_labels_path.read_text(encoding="utf-8"))
```

- [ ] **Step 3: source_gold метадані**

Замінити:
```python
        "source_gold": str(gold_labels_path),
```
на:
```python
        "source_gold": str(gold_labels_path) if gold_labels_path else None,
```

- [ ] **Step 4: ruff + наявні тести run_stage3**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/ruff check scripts/extraction/extraction_quality_eval.py && .venv/bin/python -m pytest tests/test_extraction_quality_eval.py -q`
Expected: ruff clean; `32 passed` (наявні run_stage3-тести передають Path → без змін).

- [ ] **Step 5: commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git add scripts/extraction/extraction_quality_eval.py && git commit -m "$(printf 'feat(extraction): run_stage3_aggregate приймає gold_labels_path=None\n\nБез gold-файлу gold_labels=None, source_gold=None.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: `--no-gold` прапорець + валідація + wiring + docstring

**Files:**
- Modify: `scripts/extraction/extraction_quality_eval.py`
- Test: `tests/test_extraction_quality_eval.py`

- [ ] **Step 1: тест на наявність прапорця (в кінець tests)**

```python
def test_arg_parser_has_no_gold_flag():
    from extraction.extraction_quality_eval import _build_arg_parser
    assert _build_arg_parser().parse_args(["--no-gold"]).no_gold is True
    assert _build_arg_parser().parse_args([]).no_gold is False
```

- [ ] **Step 2: прогнати — впаде (немає --no-gold)**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_extraction_quality_eval.py -q -k no_gold_flag`
Expected: FAIL (`unrecognized arguments: --no-gold`).

- [ ] **Step 3: додати `--no-gold` у `_build_arg_parser` (після блоку `--gold-only`, перед `return parser`)**

```python
    parser.add_argument(
        "--no-gold",
        action="store_true",
        default=False,
        help="Run without gold labels (gold-derived fields -> null)",
    )
    return parser
```

- [ ] **Step 4: валідація в `main()` (після `args = parser.parse_args()`)**

```python
def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    if args.no_gold and args.gold_only:
        parser.error("--no-gold та --gold-only взаємовиключні")
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_main_async(args))
```

- [ ] **Step 5: wiring у Stage 3 (`_main_async`)**

Замінити:
```python
        report = run_stage3_aggregate(
            judgements_path=judgements_path,
            gold_labels_path=Path(args.gold),
            output_path=report_path,
        )
```
на:
```python
        report = run_stage3_aggregate(
            judgements_path=judgements_path,
            gold_labels_path=None if args.no_gold else Path(args.gold),
            output_path=report_path,
        )
```

- [ ] **Step 6: docstring — додати `--no-gold` у секцію «Вхід»**

У module-docstring, після рядка про `--author / --limit / --gold-only / --stages`, додати:
```
- --no-gold: запуск без gold (gold-залежні поля missed_rate/gold_agreement → null).
```

- [ ] **Step 7: ruff + --help + повний набір**

Run:
```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && \
.venv/bin/ruff check scripts/extraction/extraction_quality_eval.py && \
.venv/bin/python scripts/extraction/extraction_quality_eval.py --help | grep -q -- --no-gold && echo "help has --no-gold" && \
.venv/bin/python -m pytest tests/ -q | tail -1
```
Expected: ruff clean; `help has --no-gold`; `210 passed`.

- [ ] **Step 8: commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git add scripts/extraction/extraction_quality_eval.py tests/test_extraction_quality_eval.py && git commit -m "$(printf 'feat(extraction): прапорець --no-gold у extraction_quality_eval\n\n--no-gold вимикає gold (взаємовиключний з --gold-only); Stage 3 передає\ngold_labels_path=None. + тест парсера, оновлено docstring.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Фінальна перевірка

- [ ] **Step 1: повний набір + ruff**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/ruff check scripts/extraction/extraction_quality_eval.py && .venv/bin/python -m pytest tests/ -q | tail -1`
Expected: ruff clean; `210 passed`.

- [ ] **Step 2: smoke `--no-gold` на наявному judgements-артефакті (якщо є; без LLM)**

Run:
```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && \
if [ -f scripts/outputs/extraction_eval/extraction_judgements.json ]; then \
  .venv/bin/python scripts/extraction/extraction_quality_eval.py --stages 3 --no-gold \
    --output-dir scripts/outputs/extraction_eval 2>&1 | tail -8 && \
  .venv/bin/python -c "import json; r=json.load(open('scripts/outputs/extraction_eval/extraction_eval_report.json')); m=next(iter(r['per_model'].values())); print('missed_rate:', m['missed_rate'], '| gold_agreement:', m['gold_agreement'], '| source_gold:', r['metadata']['source_gold'])"; \
else echo "(no judgements artifact — пропускаю; покрито юніт-тестами)"; fi
```
Expected: якщо артефакт є — Stage 3 виконується, у звіті `missed_rate: None`, `gold_agreement: None`, `source_gold: None`, а `avg_quality_score`/`hall_rate` ненульові. Якщо немає — пропуск (юніт-тести покривають).

- [ ] **Step 3: перевірка взаємовиключності (швидко)**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python scripts/extraction/extraction_quality_eval.py --no-gold --gold-only --stages 3 2>&1 | tail -2; echo "exit=$?"`
Expected: помилка argparse `--no-gold та --gold-only взаємовиключні`, ненульовий exit.

---

## Self-Review

**Spec coverage:** A (aggregate_metrics) → T1 ✓; B (run_stage3_aggregate) → T2 ✓; C (--no-gold + валідація + wiring) → T3 ✓; D (docstring) → T3 Step 6 ✓; тести no-gold → T1 Steps 1-2 + T3 Step 1 ✓; null-рішення → T1 Step 5 ✓; backward-compat (--gold дефолт) → не чіпаємо ✓.

**Placeholders:** немає — увесь код verbatim. (T2 Step 1 свідомо описує пастку «non-default after default» і фіксує фінальний варіант `gold_labels_path: Path | None` без дефолта.)

**Type consistency:** `aggregate_metrics(judgements, gold_labels=None)` ↔ виклик у `run_stage3_aggregate`; `run_stage3_aggregate(..., gold_labels_path: Path | None, ...)` ↔ виклик у `_main_async` (`None if args.no_gold else Path(args.gold)`). `args.no_gold` визначений у `_build_arg_parser`. Узгоджено.

**Ризик:** наявні тести `aggregate_metrics`/`run_stage3_aggregate` передають gold явно (list / Path) → with-gold гілка, поведінка незмінна. Підтверджено читанням фікстур.
