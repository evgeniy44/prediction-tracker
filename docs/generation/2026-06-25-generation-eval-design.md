# Generation Eval (v1) — Design

**Дата:** 2026-06-25
**Status:** 📋 designed — pre-implementation
**Контур:** перший консумер каркаса [`eval_common`](../eval-framework/2026-06-25-eval-pipeline-design.md);
оцінює генерацію `POST /answer` (`AnswerOrchestrator`).
**Дослідження:** [`2026-06-25-eval-research-summary.md`](2026-06-25-eval-research-summary.md)

> **⚠️ Scope revision (2026-06-27, після першого прогону):** generation-eval звужується до
> **ізольованої генерації на gold-контексті** — метрики лише **faithfulness + completeness**, SUT =
> половина генерації (дано gold `expected_sources`), без живого retrieval. **Refusal, off-corpus-питання,
> поріг релевантності та end-to-end RAG — ЗАПАРКОВАНО** в окремий трек (RAG-eval + retrieval threshold),
> бо refusal — властивість retrieval-handoff, не генерації. Причина: live-retrieval у v1 конфаундив
> генерацію з retrieval (completeness карав за retrieval-промахи). Секції нижче описують **v1**
> (end-to-end з refusal). **Актуальний дизайн → [2026-06-27-generation-eval-v2-design.md](2026-06-27-generation-eval-v2-design.md)**
> (ізольована генерація на **заморожених** gold-прогнозах, БД-free рантайм).

---

## Мета

Виміряти якість згенерованої RAG-відповіді (`AnswerResult{answer, sources}`) за **трьома метриками v1**:

- **faithfulness** (+hallucination) — чи сказане підкріплене джерелами. Ловить smoke-дефект «вигадана статистика».
- **refusal correctness** — чи система відповідає на питання з корпусу й відмовляє на питання поза ним. Ловить smoke-дефект «покладання на self-refusal».
- **completeness/recall** — чи відповідь покрила всі релевантні прогнози. Закриває сліпу зону faithfulness: модель може взяти одне джерело, отримати ідеальний faithfulness — і проігнорувати решту.

Eval будується **на** `eval_common`, переюзає прод-`AnswerOrchestrator`, нічого не форкає.

## Рамка рішень (узгоджено в брейнштормі)

- **Метрики v1: faithfulness + refusal + completeness/recall.** Completeness — **reference-based** (потребує
  міток «що відповідь має покрити»). Додали її з двох причин:
  - synthesis-питання без метрики повноти були б некогерентні — вони тестують мульти-source покриття, а нічого його не міряло;
  - faithfulness сам по собі — лише precision, сліпий до пропусків.

  **Відкладено:** answer relevancy (шумна, конфліктує з refusal) і citation precision (чекає маркери [n]→id). Деталі — у дослідженні.
- **Суддя — крос-родинний Claude-клас** (не Gemini-генератор → без self-preference bias). Прецедент:
  extraction-quality eval судить через `anthropic/claude-opus-4-8`.
- **Калібрування — варіант B (calibration-ready).** v1 персистить per-claim вердикти + fingerprint
  промпта + judge-id + стабільні id; ship-иться з caveat «judge-based, ще не human-calibrated». Формальне
  κ-калібрування проти людських міток — **наступний трек**.
- **SUT = реальний `AnswerOrchestrator`** → інтеграційний eval (реальний Postgres+embeddings+Gemini+Claude),
  ганяється **вручну**, коштує $. Скорери/aggregate натомість юніт-тестуються з `FakeJudge`.
- **faithfulness — один combined judge-виклик** (decompose+entail разом), не two-stage.

---

## Архітектура

Конвеєр `eval_common`: `gold → run_cases(run_one=AnswerOrchestrator) → [FaithfulnessScorer, RefusalScorer,
CompletenessScorer] → aggregate → write_report`. Generation приносить лише сабтайпи + скорери + gold +
aggregate; оркестрацію (`run_eval`), раннер, judge-гігієну, репортер бере з каркаса.

```
scripts/generation/
  build_generation_gold.py   # upstream data-transform (retrieval-gold + ручний файл → generation_gold.json)
  gen_models.py              # GenerationInput/Labels/Metrics + detail-сабмоделі
  gold.py                    # generation_gold.json → list[EvalCase]
  judge_prompts.py           # faithfulness + refusal + completeness промпти (fingerprint через eval_common)
  scorers.py                 # FaithfulnessScorer, RefusalScorer, CompletenessScorer
  metrics.py                 # aggregate(scored) → GenerationMetrics
  generation_eval.py         # main (CLI): gold → run_one(AnswerOrchestrator) → run_eval(...)
scripts/data/
  generation_manual_questions.json  # NEW, ручний (synthesis з prediction-ids + off-corpus), reviewed
  generation_gold.json              # build output
tests/
  test_generation_scorers.py        # Faithfulness/Refusal/Completeness на FakeJudge
  test_generation_metrics.py        # aggregate на фейкових ScoredRun
  test_build_generation_gold.py     # детермінований build
```

**SUT-реальність:** `generation_eval.py` потребує backfill-нутого Postgres + `GEMINI_API_KEY` (генерація)
+ `ANTHROPIC_API_KEY` (суддя). Не входить у `pytest tests/` (юніт-тести скорерів — входять).

---

## Типи даних (сабтайпи `eval_common`)

```python
class GenerationInput(BaseModel):
    question: str
    limit: int = 10

class ExpectedSource(BaseModel):
    prediction_id: str
    claim: str                            # claim_text прогнозу — щоб суддя міг перевірити покриття

class GenerationLabels(BaseModel):
    answerable: bool
    expected_sources: list[ExpectedSource] = []   # що відповідь МАЄ покрити (recall); single=1, synthesis=2-3
    category: str                         # single_source | synthesis | off_domain | near_domain

# SUT-результат = наявний AnswerResult{query, answer, sources: list[RetrievedPrediction]}

class ClaimVerdict(BaseModel):
    claim: str
    supported: bool
    reason: str

class FaithfulnessDetail(BaseModel):       # → ScoreCard.detail (faithfulness)
    claims: list[ClaimVerdict]

class RefusalDetail(BaseModel):            # → ScoreCard.detail (refusal)
    refused: bool
    answerable: bool
    category: str

class SourceCoverage(BaseModel):
    prediction_id: str
    covered: bool
    reason: str

class CompletenessDetail(BaseModel):       # → ScoreCard.detail (completeness)
    coverage: list[SourceCoverage]

class CategoryMetrics(BaseModel):          # розбивка по category
    n: int
    faithfulness_mean: float | None
    recall_mean: float | None
    refusal_accuracy: float

class GenerationMetrics(BaseModel):
    n_total: int
    n_answered: int
    n_refused: int
    n_errors: int
    faithfulness_mean: float | None        # по answered-answerable
    hallucination_rate: float | None       # = 1 - faithfulness_mean
    recall_mean: float | None              # completeness, по answered-answerable
    refusal_accuracy: float                # по всіх із answerable-міткою
    over_refusal_rate: float               # answerable → відмовив
    false_answer_rate: float               # off-corpus → відповів (найнебезпечніше)
    by_category: dict[str, CategoryMetrics]
```

`EvalCase.input = GenerationInput`, `EvalCase.labels = GenerationLabels`. Усі поліморфні поля каркаса —
`SerializeAsAny`, тож усі detail-сабмоделі (`FaithfulnessDetail`/`RefusalDetail`/`CompletenessDetail`)
виживають у `report.json` (основа calibration-ready).

---

## Gold-датасет

**Склад (~112):**
- ~**80 single-source answerable** — з `retrieval_query_gold.json` (80 унікальних прогнозів). `category=single_source`; `expected_sources=[той прогноз]`.
- ~**12 synthesis answerable** — ручні ширші питання, **побудовані з 2-3 КОНКРЕТНИХ прогнозів корпусу** → `expected_sources` відомі **за побудовою**, без окремої розмітки. `category=synthesis`.
- ~**20 off-corpus unanswerable** — ручні: `off_domain` (явно поза доменом) + `near_domain` (близько, але без відповіді). `expected_sources=[]`.

**`build_generation_gold.py` — контракт** (чистий data-transform, **без LLM/мережі**, детермінований):
- **Входи** (три файли):
  - `retrieval_query_gold.json` — `{query, target_id, source_field}`;
  - `generation_manual_questions.json` — `{question, category, prediction_ids}`; поле `prediction_ids` непорожнє лише для synthesis;
  - `retrieval_eval_corpus.json` — прогнози з `claim_text`, щоб збагатити `expected_sources` текстом клейму.
- **Single-source:** згрупувати retrieval-gold за `target_id`; **50/50 phrasing** — сортувати target_id, парний індекс → `claim_text`-фраза, непарний → `situation`-фраза (одне питання/прогноз, ~40 claim + ~40 situation). НЕ «prefer claim_text» (бо відсікло б усі situation). `expected_sources=[{target_id, claim з корпусу}]`.
- **Synthesis:** `expected_sources` = `prediction_ids`, кожен збагачений `claim` із корпусу; `answerable=true`.
- **Off-corpus:** `answerable=false`, `expected_sources=[]`.
- **Вихід** `generation_gold.json`: `[{id, question, answerable, expected_sources:[{prediction_id, claim}], category}]`, стабільні id (`a<NNN>` answerable за target_id; `o<NNN>` off).
- **Валідація:** усі `prediction_ids` існують у корпусі — інакше fail-loud (мітка без `claim` безглузда для completeness).

---

## Скорери (сигнатури + поведінка, без тіл)

### `FaithfulnessScorer(Scorer)` — `scorers.py`

```python
class FaithfulnessScorer:
    name = "faithfulness"
    def __init__(self, judge: Judge) -> None: ...
    async def score(self, run: EvalRun) -> ScoreCard: ...
```

**Коли рахуємо faithfulness, а коли — N/A.**
Міряємо лише для answerable-питань. Скорер повертає `ScoreCard(score=None)` (N/A — не входить у
faithfulness-mean) у трьох випадках:
1. система впала, відповіді нема (`run.result is None`);
2. питання поза корпусом (`not labels.answerable`);
3. з відповіді не вийшло жодного фактичного твердження.

Випадок 3 — навмисний: **відмова** («не можу відповісти») не містить фактів → 0 тверджень → N/A. Тобто
скорер сам пропускає відмови, і йому **не треба окремо визначати «це відмова чи ні»** — це вже робить
`RefusalScorer`. Так ми не дублюємо ту логіку (інакше два скорери могли б по-різному вирішити, що є відмовою).

**Як рахуємо (коли застосовна):**
- **Один combined judge-виклик** (промпт у `judge_prompts.py`): «розклади `answer` на атомарні твердження
  й познач кожне supported/ні проти sources». Sources рендеряться в текст (id + claim_text + situation +
  status кожного `RetrievedPrediction`).
- `total` = скільки атомарних тверджень суддя виділив із відповіді; `supported` = скільки з них
  підкріплені sources. **`score = supported / total`** — частка відповіді, що ґрунтується на джерелах
  (faithfulness однієї відповіді). `detail = FaithfulnessDetail(claims=[...])` несе всі твердження з вердиктами.
- Суддя — DI через `Judge` Protocol (у тестах `FakeJudge`).

### `RefusalScorer(Scorer)` — `scorers.py`

```python
class RefusalScorer:
    name = "refusal"
    def __init__(self, judge: Judge) -> None: ...
    async def score(self, run: EvalRun) -> ScoreCard: ...
```

**Поведінка:**
Застосовна до **всіх** кейсів (кожен має мітку `answerable`). Якщо система впала (`run.result is None`) → N/A.

**Як визначаємо, що система відмовилась** — два кроки:
1. **Дешева точна перевірка.** Чи відповідь дослівно дорівнює канонічному тексту відмови? `AnswerOrchestrator`
   повертає сталий рядок `REFUSAL_NO_DATA`, коли нічого не знайшов — це «жорстка» відмова, ловиться без LLM.
2. **Якщо ні — питаємо суддю.** Модель могла відмовити «своїми словами» («не можу відповісти за наявними
   даними»). Тоді один дешевий yes/no до судді: «це відмова?».

**Оцінка.** `score = 1.0`, якщо рішення системи правильне: відповіла на answerable, або відмовила на
off-corpus. Інакше `0.0`. `detail = RefusalDetail(refused, answerable, category)`.

### `CompletenessScorer(Scorer)` — `scorers.py`

```python
class CompletenessScorer:
    name = "completeness"
    def __init__(self, judge: Judge) -> None: ...
    async def score(self, run: EvalRun) -> ScoreCard: ...
```

**Коли рахуємо, а коли N/A.** Повертає `ScoreCard(score=None)` (N/A) якщо `run.result is None` **або**
`not labels.answerable` (off-corpus не має чого «покривати»). Інакше — рахує **на всіх answerable**,
включно з over-refusal (відмова на answerable → recall ≈ 0, що **коректно**: вона не покрила нічого).

**Чому інша обробка відмов, ніж у faithfulness** (це не суперечність — різні питання):
- faithfulness питає «чи правда те, що сказано?» → відмова не каже фактів → N/A;
- completeness питає «чи покрито потрібне?» → відмова покрила 0 → recall 0.

**Як рахуємо:** для кожного `ExpectedSource` — окремий **judge yes/no**: «чи відображено клейм
`<expected.claim>` у відповіді `<answer>`?» → `covered`. `recall = covered / len(expected_sources)`;
`detail = CompletenessDetail(coverage=[SourceCoverage{prediction_id, covered, reason}])`. Вартість:
`len(expected_sources)` judge-викликів на answerable-кейс (single=1, synthesis=2-3).

---

## Суддя

`build_eval_llm("anthropic/claude-...", temperature=0)` → `LLMJudge(llm, judge_id)`. Один суддя на всі три
скорери (faithfulness decompose+entail; refusal yes/no; completeness per-source yes/no). Промпти
**fingerprint-яться** (`fingerprint_prompt`) у `EvalMetadata.prompt_fingerprints`; `judge_id` у metadata.
Рубрики бінарні (supported/ні, covered/ні) — мало чутливі до порядку, тож `shuffle_options` у v1 опційно.

---

## Aggregate → GenerationMetrics

`aggregate(scored: list[ScoredRun]) -> GenerationMetrics` (чиста функція, без LLM):
- **faithfulness_mean / hallucination_rate** — лише по картках faithfulness зі `score is not None`
  (answered-answerable). `hallucination_rate = 1 - faithfulness_mean`.
- **recall_mean** — по картках completeness зі `score is not None` (answered-answerable).
- **refusal:** з `RefusalDetail` — `refusal_accuracy`; `over_refusal_rate` (answerable & refused / answerable);
  `false_answer_rate` (!answerable & !refused / !answerable).
- **by_category** (`CategoryMetrics` на кожну з `single_source`/`synthesis`/`off_domain`/`near_domain`):
  faithfulness_mean, recall_mean (де застосовно), refusal_accuracy, n. Тут видно, чи синтез слабший за single-source.
- counts: `n_total/n_answered/n_refused/n_errors`.

---

## Потік даних та обробка помилок

| Ситуація | Поведінка | Де |
|----------|-----------|-----|
| SUT впав (`run.result is None`) | усі три скорери → `ScoreCard(score=None)`; `n_errors++` | scorers/aggregate |
| Answerable, система відмовилась (over-refusal) | faithfulness N/A (0 claims); completeness recall≈0; refusal score=0 | scorers |
| Off-corpus, система відповіла (false-answer) | faithfulness N/A (не answerable); completeness N/A (не answerable); refusal score=0 | scorers |
| Judge непарсибельний вихід | retry в `LLMClient`; вичерпано → виняток у скорері спливає (run_eval не ловить scorer-винятки у v1) | judge |
| Порожній gold | `run_eval` → звіт `n=0` | eval_common |

**Логування** (per [[python-logging]]): per-module `logger`, прогрес кожні N, без payload (тексти питань/
відповідей/судді не логуються).

---

## Calibration-ready (варіант B)

v1 видає все, що формальному κ-калібруванню потрібне, окрім людських міток:
- **per-claim вердикти** (`FaithfulnessDetail`) + refusal-рішення (`RefusalDetail`) + per-source покриття (`CompletenessDetail`) — у `report.json`;
- **fingerprint промпта + judge_id** — у `metadata`;
- **стабільні `EvalCase.id`** — для join людських міток.

Звіт містить caveat: **«judge-based, ще не human-calibrated»**. Збір людських UA-міток + обрахунок κ —
наступний трек (свій design/plan).

---

## Тестування

- **Скорери** — юніт із `FakeJudge` (канонічний вердикт) + фікстур-`AnswerResult`: faithfulness рахує
  supported/total + N/A на 0-claims/None; refusal — confusion 4 квадрантів; completeness рахує
  covered/expected + N/A на off-corpus/None. Без мережі.
- **aggregate** — юніт на фейкових `ScoredRun` (per-category, edge: 0 answered, усі refused, recall зі змішаних None/значень).
- **build_generation_gold** — детермінований юніт (50/50 split, стабільні id, дедуп).
- **generation_eval.py** — ручний інтеграційний прогон (реальна інфра, $); у `pytest tests/` НЕ входить.

---

## Свідомо поза скоупом / відкладено

- **Answer relevancy** — наступні цикли (шумна; конфліктує з refusal).
- **Citation precision + маркерні цитати [n]→id** — окремо; маркери розблоковують per-claim citation precision (recall покрито completeness'ом v1).
- **RAGChecker тонкий noise-спліт** (relevant/irrelevant-noise) — потребує gold-міток релевантності джерел.
- **Формальне κ-калібрування судді** — наступний трек (v1 лише calibration-ready).
- **Поріг релевантності для refusal** — продуктовий фікс, окремо; цей eval його **вимірює** (refusal-метрика).

## Відкриті питання

1. Чи рандомізувати порядок у faithfulness-рубриці у v1 (бінарна supported/ні мало чутлива) — схиляюсь ні.
2. Точна модель-суддя (`claude-opus-4-8` як extraction-quality, чи дешевший Claude/Gemini-Pro) — рішення на момент прогону, конфігуровано через `--judge`.
3. Чи виключати synthesis-кейси з faithfulness-mean окремо (вони стресовіші) — звітуємо by_category, рішення за даними.
4. Completeness: чи «covered» бінарне, чи допускати «частково покрито» (напр. 0.5) — v1 бінарне; толерантність до перефразування лишаємо судді (yes/no «чи відображено клейм»).

## Зв'язок

- Каркас: [`eval_common`](../eval-framework/2026-06-25-eval-pipeline-design.md) — ролі/типи/`run_eval`.
- Пайплайн під тестом: `AnswerOrchestrator` (`POST /answer`), [`2026-06-22-generation-design.md`](2026-06-22-generation-design.md).
- Gold-насіння: `retrieval_query_gold.json` (з retrieval-eval треку).
- Методологія судді: дослідження + [[llm-as-judge]] / [[multilingual-llm-judge]] (Brain wiki).
