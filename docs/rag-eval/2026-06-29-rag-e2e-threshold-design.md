# End-to-end RAG eval + relevance threshold — Design

**Дата:** 2026-06-29
**Status:** 📋 designed — pre-implementation
**Контур:** розпарк треку, відкладеного при ізоляції генерації (чип `task_a358c756`).
**Спирається на:** [generation-eval v2](../generation/2026-06-27-generation-eval-v2-design.md) (scorer-и, gold), [retrieval-eval](../retrieval-eval/2026-06-19-retrieval-eval-design.md) (вибір embedding-моделі), [`eval_common`](../eval-framework/2026-06-25-eval-pipeline-design.md).

---

## Мета

Закрити дві прогалини, які лишилися після ізоляції генерації:

1. **Поріг релевантності (A).** Зараз `QueryOrchestrator.search` повертає top-k без порога → на off-topic питання система все одно отримує найближчі-але-нерелевантні прогнози й покладається на self-refusal Gemini (недетерміновано). **Поріг** на `distance` робить refusal детермінованим **retrieval-рішенням**.
2. **End-to-end якість (B).** Ізольований eval довів: дано правильний контекст — генерація ~0.98. Але в проді контекст обирає retrieval, **не виміряний** для answer-питань. B ганяє **справжній прод-шлях** і міряє його якість.

Скоуп — **обидва, послідовно**: A налаштовує поріг (дешево, детерміновано) → B тестує end-to-end із цим порогом.

## Рамка рішень

- **Два окремі скрипти** в новому пакеті `scripts/rag/`: A (retrieval-only sweep) + B (повний answer). Чисте розділення: A дешевий/детермінований/rerunnable; B важкий (LLM+суддя), переюзає generation-eval scorer-и.
- **Переюз gold:** наявний `generation_gold.json` (92 answerable з `expected_sources` + 20 off-corpus: 10 off_domain + 10 near_domain) — рівно те, що треба обом.
- **Об'єктив порога — trust-first:** max off-corpus-refusal за умови answerable-recall ≥ ~0.9. Краще зайва відмова, ніж впевнена відповідь на off-topic (для fact-checker довіра > покриття). Звіт — **повна крива** по всіх T; об'єктив лише обирає робочу точку.
- **Поріг — у конфіг** (`Settings.relevance_threshold`), застосовується в `QueryOrchestrator.search`. A передає `None` (сирий top-k для sweep); прод/B беруть налаштоване значення.

## Передумова (критична)

Обидва скрипти роблять **живий vector-search по прод-корпусу** → потрібні **backfill embeddings** (зараз історично всі `embedding IS NULL`). Без backfill A/B повертають порожнечу/сміття. Backfill-скрипт уже є (`is_embedding_present` → ідемпотентний); прогнати на проді — крок 0 виконання.

---

## A — `scripts/rag/threshold_eval.py` (retrieval-only)

**Runner** (`eval_common.run_cases`): orchestrator збудований із `threshold=None` (сирий top-k); на кожне gold-питання → `QueryOrchestrator.search(question, limit=N)` → `QueryResult` (ранжовані `RetrievedPrediction` з `distance`). Без генерації, без судді. N достатньо великий (напр. 20), щоб sweep мав запас. Поріг T застосовує вже sweep, не retrieval.

**Sweep** (`sweep_thresholds(runs, cases) -> ThresholdReport`): для сітки T (по фактичному діапазону distance) рахуємо, з розбивкою по category:
- **off-corpus refusal-rate(T)** = частка off-corpus-кейсів із 0 matches `distance ≤ T`;
- **answerable answer-rate(T)** = частка answerable із ≥1 match `≤ T`;
- **retrieval-recall(T)** = частка answerable, де **очікуване** джерело (`expected_sources[].prediction.id`) серед matches `≤ T`. Це й перший вимір **абсолютного** retrieval-recall (known-item-eval давав лише відносний).

**Вибір T:** найбільший off-corpus-refusal-rate за умови `answerable retrieval-recall ≥ 0.9`. Якщо умова недосяжна — звіт це показує (retrieval сам слабкий → лагодити retrieval, не поріг).

**Чому без scorer-ів:** sweep — агрегатна операція над усіма distance одразу, не per-case вердикт. Тож A = `run_cases` + чиста функція `sweep_thresholds` + markdown/JSON-звіт. Повністю детерміновано (ембединги фіксовані).

**Вихід:** `ThresholdReport` — крива {T → метрики by_category} + обраний `relevance_threshold`.

---

## B — `scripts/rag/e2e_eval.py` (end-to-end, повний answer)

**Runner:** `AnswerOrchestrator.answer(question, limit)` — **жива retrieval із налаштованим порогом** → генерація → `AnswerResult`. Refusal детермінований (порожньо після порога → `REFUSAL_NO_DATA`).

**Scorer-и** (`eval_common`, суддя — Claude Opus, як у generation-eval):
- **RefusalScorer** (воскрешаємо з generation-eval v1): off-corpus → має відмовити; answerable → має відповісти. Дає refusal-accuracy / over-refusal / false-answer.
- **FaithfulnessScorer** (переюз generation-eval як є): claim-и відповіді проти **знайдених** `run.result.sources` (з фіксом status-авторитету). Міряє «чи генерація не вигадала поза поданим».
- **CompletenessScorer (e2e-варіант, vs gold):** проти **`labels.expected_sources`** (не знайдених) → **end-to-end recall**: скільки з того, що МАЛО бути покрито, фінальна відповідь донесла. Свідомо конфаундовано retrieval-ом (якщо retrieval не знайшов джерело — відповідь його не покриє). Це й є сенс end-to-end. Відрізняється від v2-completeness (та судить подане); тож B-completeness — варіант скорера з джерелом `gold` замість `fed`.

**Метрики `RagE2EMetrics`:** `n_total`, `n_errors`, `refusal_accuracy`, `over_refusal_rate`, `false_answer_rate`, `faithfulness_mean`, `hallucination_rate`, `end_to_end_recall_mean`, `by_category`.

---

## Поріг — прод-зміна (`src/`)

- `Settings.relevance_threshold: float | None = None` (None = поточна поведінка top-k без порога; ставимо значення після A).
- `QueryOrchestrator` приймає `relevance_threshold` (через factory з `Settings`); `search` після `search_similar` **відкидає matches з `distance > threshold`**. Порожньо → `QueryResult.results == []` → `AnswerOrchestrator` → `REFUSAL_NO_DATA`.
- A будує orchestrator із `threshold=None` (sweep сам застосовує T); B/прод — із налаштованим.

Сигнатури не ламаються (threshold опціональний, дефолт None).

---

## Декомпозиція (навіщо A і B разом)

`A.retrieval_recall` (retrieval **знайшов** очікуване) vs `B.end_to_end_recall` (відповідь **донесла** очікуване). Розрив = втрата на генерації. Якщо `A.retrieval_recall` низький — пляшкове горло саме retrieval (лагодити його), і B-якість обмежена згори. Так два числа локалізують, де втрачаємо.

## Потік даних та краї

| Ситуація | Поведінка |
|----------|-----------|
| embeddings не backfill'нуті | retrieval порожній → усе «відмова» → звіт явно деградований (передумова не виконана) |
| off-corpus, 0 matches ≤ T | A: правильна відмова; B: `REFUSAL_NO_DATA`, refusal correct |
| answerable, очікуване джерело не в top-N | A: retrieval-recall miss; B: end-to-end recall падає (retrieval-винний) |
| LLM/суддя впав (лише B) | `EvalRun(result=None)` → scorer-и N/A; `n_errors++` |
| A | нуль LLM → нуль таких помилок |

## Тестування

- **A `sweep_thresholds`** — unit на фікстурах (синтетичні runs+distances): refusal-rate / answer-rate / retrieval-recall на відомих порогах; вибір T за trust-first-правилом; крайові (усі ≤ T, усі > T).
- **B RefusalScorer** — unit (FakeJudge / hard-path `REFUSAL_NO_DATA`): off vs answerable × refused vs answered.
- **B CompletenessScorer e2e-варіант** — unit: судить проти `labels.expected_sources` (не fed); guard N/A на off-corpus.
- **QueryOrchestrator threshold** — unit (FakeVectorStore): matches з `distance > threshold` відкидаються; `None` → без фільтра (поточна поведінка).
- **A/B CLI** — без юніту (інтеграція; ручний прогін на проді з backfill).

## Скоуп

**In:** пакет `scripts/rag/`; A (threshold sweep + вибір) ; B (end-to-end answer + refusal/faithfulness/e2e-recall); прод-поріг у `QueryOrchestrator`/`Settings`; e2e-варіант CompletenessScorer; воскресіння RefusalScorer; unit-тести.

**Out (deferred):**
- розширення off-corpus gold (зараз лише 20 — мало для робастного порога; near_domain — ключовий дискримінатор) — окремий data-крок, якщо крива шумна;
- hybrid-search / метадані-фільтри (Phase 2);
- формальне κ-калібрування судді (окремий трек);
- автоматичне виставлення порога в конфіг (зараз — ручний крок за звітом A).

## Зв'язок

- Парк-джерело: чип `task_a358c756`.
- gold + scorer-и: [generation-eval v2](../generation/2026-06-27-generation-eval-v2-design.md).
- retrieval-конфіг (embedding+repr): [retrieval-eval](../retrieval-eval/2026-06-19-retrieval-eval-design.md).
- каркас: [`eval_common`](../eval-framework/2026-06-25-eval-pipeline-design.md).
