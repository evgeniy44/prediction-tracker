# Generation Eval v2 — Design (isolated generation on frozen gold context)

**Дата:** 2026-06-27
**Status:** 📋 designed — pre-implementation (adversarial-reviewed)
**Контур:** ревізія [v1](2026-06-25-generation-eval-design.md) після першого прогону.
**Каркас:** [`eval_common`](../eval-framework/2026-06-25-eval-pipeline-design.md)

---

## Навіщо ревізія

v1 ганяв реальний `AnswerOrchestrator.answer` (retrieval у живій БД → генерація), тобто тестував **увесь
RAG**, не генерацію. Конфаунд підтверджено на першому прогоні: completeness карав генератор за
**retrieval-промахи**, а faithfulness ~0.5 частково через шум 10 retrieved джерел.

**v2 ізолює генерацію:** годуємо генератор **gold-контекстом** (саме ті прогнози, які відповідь має
покрити) і міряємо лише те, що залежить від генератора. **Refusal + поріг + end-to-end RAG —
ЗАПАРКОВАНО** окремим треком (чип `task_a358c756`).

## Рамка рішень

- **Метрики: faithfulness + completeness.** Refusal видалено.
- **SUT = половина генерації** (`answer_from_sources`), без embedding/search.
- **Gold-контекст ЗАМОРОЖЕНО в датасеті:** `expected_sources` несе **повні `Prediction`-и**, вичитані з БД
  **один раз під час build**. Eval-runtime **БД-free** і **відтворюваний** (той самий gold → ті самі
  числа; різниця = лише модель/промпт, не дрейф БД). Заморожений контент = **єдине джерело правди** і для
  генератора, і для судді → нема claim-divergence.
- **Прод-код не форкаємо:** виносимо `answer_from_sources` з `answer`.

---

## Архітектура

```
answerable-кейс (gold)
  → expected_sources[].prediction         # ЗАМОРОЖЕНІ повні Prediction (з gold, не з БД)
  → wrap у RetrievedPrediction(distance=0, rank=i)
  → AnswerOrchestrator.answer_from_sources(question, sources)   # generate-only, лише LLM
  → AnswerResult (sources = ті самі подані прогнози)
  → [FaithfulnessScorer, CompletenessScorer]
  → aggregate → write_report
```

У рантаймі евалу: **нема БД, нема embedder, нема retrieval**. Зовнішні виклики — лише LLM-генератор +
LLM-суддя.

---

## Зміна 1 — `AnswerOrchestrator` split (прод, `query/answer_orchestrator.py`)

Виносимо generate-only половину; `answer` делегує. Поведінка прод-`answer` **не змінюється**.

```python
class AnswerOrchestrator:
    def __init__(self, llm: LLMClient, query_orchestrator: QueryOrchestrator | None = None) -> None: ...
    async def answer_from_sources(self, question: str, sources: list[RetrievedPrediction]) -> AnswerResult: ...
    async def answer(self, question: str, limit: int = 10) -> AnswerResult: ...
```

**`query_orchestrator` стає опціональним** — `answer_from_sources` його не потребує (лише `llm` +
`build_rag_prompt`), тож eval будує orchestrator **без** retrieval-стека. `answer` потребує його; якщо
`None` — кидає зрозумілий `RuntimeError`.

**Поведінка `answer_from_sources`:** порожні `sources` → `AnswerResult(REFUSAL_NO_DATA, [])`; інакше
`build_rag_prompt(question, sources)` + `llm.complete(RAG_SYSTEM)` → `AnswerResult(answer=..., sources=sources)`.
**`answer`:** `search` → делегує. **Лог-префікс** оновити на `"answer_from_sources:"`. Прод-фабрику
`build_answer_orchestrator` оновити під новий конструктор. (Повні тіла — у плані.)

---

## Зміна 2 — eval generate-only, БД-free (`scripts/generation/generation_eval.py`)

Eval будує **тільки LLM-генератор** (без repo/embedder/session):

```python
llm = LLMClient(provider="gemini", model="gemini-3.1-flash-lite-preview",
                api_key=settings.gemini_api_key, temperature=0)
orchestrator = AnswerOrchestrator(llm)   # generate-only, query_orchestrator=None
```

**`run_one`** — джерела беремо з **замороженого** gold (нуль БД):
```python
sources = [RetrievedPrediction(prediction=es.prediction, distance=0.0, rank=i)
           for i, es in enumerate(case.labels.expected_sources, 1)]
return await orchestrator.answer_from_sources(case.input.question, sources)
```
`build_rag_prompt` ігнорує `distance`/`rank` → синтетичні значення безпечні (підтверджено).

**Фільтр answerable — у `_main`** (після `load_generation_gold`):
`cases = [c for c in cases if c.labels.answerable]`. Off-corpus off_domain/near_domain пропускаються
(для парк-треку).

---

## Зміна 3 — gold несе заморожені прогнози; build читає БД

- **`ExpectedSource` → `{prediction: Prediction}`** (повний заморожений прогноз; окреме поле `claim` зайве —
  це `prediction.claim_text`).
- **`build_generation_gold.py`** додає **єдину** залежність — читає БД раз, щоб вкласти повні прогнози:
  за expected-id-ами (single-source `target_id`; synthesis `prediction_ids`) → `get_by_ids` → серіалізує
  `Prediction` у `expected_sources`. (Решта build-логіки — 50/50 phrasing тощо — без змін.) Build —
  upstream-крок, не рантайм; його DB-залежність прийнятна, бо вихід (gold) — заморожений.
- **`gold.py`** десеріалізує `Prediction` усередині `ExpectedSource`.
- **Off-corpus** записи `expected_sources=[]` (без змін).

---

## Зміна 4 — CompletenessScorer судить проти ПОДАНИХ джерел (`scorers.py`)

v1 ітерував `labels.expected_sources[].claim`. Тепер судимо проти **фактично поданих** `run.result.sources`
(= ті самі заморожені прогнози, що бачив генератор) → judged-claim **тотожний** fed-claim:

```python
async def score(self, run):
    if run.result is None or not run.result.sources:   # порожні sources = refusal → N/A
        return ScoreCard(scorer=self.name, score=None)
    coverage = []
    for s in run.result.sources:
        p = s.prediction
        covered, reason = parse_completeness_response(await judge.assess(
            build_completeness_prompt(run.result.answer, claim=p.claim_text, situation=p.situation),
            system=COMPLETENESS_SYSTEM))
        coverage.append(SourceCoverage(prediction_id=p.id, covered=covered, reason=reason))
    score = sum(c.covered for c in coverage) / len(coverage)
    return ScoreCard(scorer=self.name, score=score, detail=CompletenessDetail(coverage=coverage))
```

**`build_completeness_prompt(answer, claim, situation)`** — `situation` передається судді як
**дезамбігуючий контекст** (claim-и часто неоднозначні: «вони не зможуть»), щоб він коректно
ідентифікував прогноз. «Покриття» = прогноз відображено; ситуацію переказувати **не вимагаємо**
(метадані date/status/confidence до судді не йдуть — їх покривати не треба). Це вирівнює з faithfulness,
який і так бачить повне джерело через `render_sources`.

З замороженим контентом divergence неможливий (fed == frozen == judged); guard `not sources` лишається
запобіжником.

---

## Зміна 5 — видалення refusal (повний removal-список)

| Файл | Видаляємо |
|------|-----------|
| `scorers.py` | `RefusalScorer` |
| `judge_prompts.py` | `REFUSAL_SYSTEM`, `build_refusal_prompt`, `parse_refusal_response` |
| `gen_models.py` | `RefusalDetail`; з `GenerationMetrics` — `n_answered`/`n_refused`/`refusal_accuracy`/`over_refusal_rate`/`false_answer_rate`; з `CategoryMetrics` — `refusal_accuracy`. **`ExpectedSource`: `claim: str` → `prediction: Prediction`** |
| `metrics.py` | **атомарно з gen_models:** refusal-init, `"refusal"` ключ у `by_cat`-bucket, refusal-гілка циклу, refusal-поля в конструкторах `CategoryMetrics`/`GenerationMetrics` |
| `generation_eval.py` | import+usage `RefusalScorer`; import `REFUSAL_SYSTEM`; `"refusal"` у `prompt_fingerprints`; `"embedder"` у `sut_models`; import `build_answer_orchestrator` (замінено прямим LLM-build); argparse `description` («+ refusal» прибрати). `Settings` лишається лише заради `gemini_api_key` (БД-free → `database_url` не потрібен) |
| `tests/test_generation_scorers.py` | refusal-тести; **оновити completeness-тест** під `run.result.sources` + новий `ExpectedSource` |
| `tests/test_generation_metrics.py` | refusal-асерти + рефактор `_scored` (без `RefusalDetail`/refusal-`ScoreCard`) |
| `tests/test_generation_judge_prompts.py` | `test_parse_refusal_response` + import `parse_refusal_response` |
| `tests/test_generation_gold.py`, `test_build_generation_gold.py` | оновити під `ExpectedSource{prediction}` + DB-fetch у build |

`REFUSAL_NO_DATA` лишається. `scripts/eval_common/report.py` не чіпаємо (`model_dump_json` без доступу за іменем — підтверджено).

---

## Типи (після ревізії)

```python
class ExpectedSource(BaseModel):
    prediction: Prediction          # заморожений повний прогноз

class CategoryMetrics(BaseModel):
    n: int
    faithfulness_mean: float | None
    recall_mean: float | None

class GenerationMetrics(BaseModel):
    n_total: int
    n_errors: int
    faithfulness_mean: float | None
    hallucination_rate: float | None
    recall_mean: float | None
    by_category: dict[str, CategoryMetrics]
```
`GenerationLabels`/`FaithfulnessDetail`/`ClaimVerdict`/`SourceCoverage`/`CompletenessDetail` — без змін.

---

## Метрики (семантика чиста)

- **faithfulness** = supported/total claims проти gold-контексту (без retrieval-шуму).
- **completeness/recall** = covered/fed (= expected) — recall=0 означає **генератор пропустив**.
- **by_category:** `single_source` vs `synthesis`.

---

## Потік даних та обробка помилок

| Ситуація | Поведінка | Де |
|----------|-----------|-----|
| expected-id не знайдено в БД | **build fail-loud** (`KeyError`/явна помилка) — мітка без прогнозу безглузда | build (не рантайм) |
| SUT/LLM впав | `EvalRun(result=None)` → обидва scorer-и N/A; `n_errors++` | рантайм |
| Judge непарсибельний | retry в `LLMClient`; вичерпано → виняток спливає (як v1) | рантайм |

Рантайм **не має** БД-помилок (контент заморожено). Логування/прогрес — з `run_cases`/`run_eval`.

---

## Тестування

- **scorers** — Faithfulness + Completeness (FakeJudge); прибрати refusal; **оновити completeness-тест** під
  `run.result.sources` (фідстворювати `AnswerResult` із sources) + новий `ExpectedSource{prediction}`.
- **metrics** — `aggregate`/`_scored` без refusal.
- **build_generation_gold** — тест із **фейковим repo** (in-memory `get_by_ids`), детермінований.
- **новий unit — `answer_from_sources`** (прод): порожні→refusal; непорожні→`build_rag_prompt`+`complete` (fake LLM).
- `generation_eval.py` — без юніту (інтеграція; ручний прогін, тепер БД-free на стороні генерації — лише API-ключі генератора+судді).
- Сюїта зелена; атомарні коміти gen_models+metrics.

---

## Свідомо поза скоупом

- **Refusal, off-corpus, поріг релевантності, end-to-end RAG** — парк-трек (чип `task_a358c756`).
- **Answer relevancy, citation precision/маркери** — наступні цикли.
- **Формальне κ-калібрування судді** — наступний трек (v2 calibration-ready).
- **Noise-robustness генерації** — RAG-трек.

## Зв'язок

- v1: [2026-06-25-generation-eval-design.md](2026-06-25-generation-eval-design.md).
- Каркас: [eval_common](../eval-framework/2026-06-25-eval-pipeline-design.md).
- Парк-трек: чип `task_a358c756`.
