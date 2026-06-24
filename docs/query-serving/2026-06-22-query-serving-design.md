# Query Serving (RAG retrieval-only) — Design

**Дата:** 2026-06-22
**Status:** 📋 designed — pre-implementation
**Контур:** retrieval-частина RAG query-флоу
([`../architecture/2026-04-26-flow-production-rag.md`](../architecture/2026-04-26-flow-production-rag.md)) — без генерації.

---

## Мета

Перетворити питання природною мовою на **ранжований список релевантних прогнозів** із БД:
`query → embed → search → fetch → ранжовані прогнози`. Подається через `POST /query`.

## Рамка рішень (узгоджено в брейнштормі)

- **Retrieval-only, gen-ready.** Жодної LLM-генерації відповіді — це окремий цикл v1.5
  (через її окрему планку якості: faithfulness / citation / refusal, LLM-as-judge). Шов чистий:
  `search()` повертає `QueryResult`, генерація сяде зверху як `answer(QueryResult) → str`.
- **Чистий ранжир: завжди top-k + score, без порога.** Поріг релевантності (cosine-distance
  cutoff) зараз був би непідібраним магічним числом (eval запарковано) → відкладається до v1.5,
  де тюниться по gold. Споживач бачить `distance` і може відсікати сам.
- **Без метаданих-фільтрів** (status/person/date) — Phase 2 (hybrid search). Корпус однолюдний.
- **Типізовані межі** (CLAUDE.md): усі повернення — іменовані Pydantic-моделі, не tuple/dict.

## Архітектура

Ports-and-adapters, новий пакет `query/`, що дзеркалить `IngestionOrchestrator` /
`VerificationOrchestrator`. Власна композиція у `factory.py`, endpoint у `app.py` через `lifespan`.

```
POST /query {question, limit}
        │
        ▼
QueryOrchestrator.search(question, limit)
        │  embed(question)            ← EmbeddingClient (LiteLLM)
        │  search_similar(vec, limit) ← VectorStore → list[VectorMatch] (id + distance, відсортовано)
        │  get_by_ids([id...])        ← PredictionRepository → list[Prediction] (у порядку id)
        ▼
QueryResult {query, results: [RetrievedPrediction{prediction, distance, rank}]}
```

## Доменні моделі (`models/domain.py`)

```python
class VectorMatch(BaseModel):
    prediction_id: str
    distance: float          # cosine-distance: менше = ближче

class RetrievedPrediction(BaseModel):
    prediction: Prediction
    distance: float
    rank: int                # 1-based, порядок за схожістю

class QueryResult(BaseModel):
    query: str
    results: list[RetrievedPrediction]
```

## Компоненти та файли

### 1. `VectorStore.search_similar` → `list[VectorMatch]`
`storage/interfaces.py` (Protocol), `storage/postgres.py` (impl), `tests/fakes.py` (fake), 1 тест.
Зміна **in place** (прод-споживачів немає; CLAUDE.md:86). Impl додає `distance` у `select`:
```python
dist = PredictionDB.embedding.cosine_distance(query_embedding)
stmt = select(PredictionDB.id, dist.label("distance")).order_by(dist).limit(limit)
return [VectorMatch(prediction_id=r[0], distance=r[1]) for r in result.all()]
```

### 2. `PredictionRepository.get_by_ids(ids) -> list[Prediction]` — NEW
`storage/interfaces.py` + `storage/postgres.py` + `tests/fakes.py`. Контракт: **повертає у порядку
вхідних `ids`** (бо `WHERE id IN (…)` порядок не гарантує, а ранг зі `search_similar` треба
зберегти). Відсутні id мовчки пропускаються (не помилка). Impl: `SELECT … WHERE id = ANY(:ids)`,
далі перевпорядкувати в Python за `ids`.

### 3. `QueryOrchestrator` (`query/orchestrator.py`) — NEW
```python
class QueryOrchestrator:
    def __init__(
        self,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
        prediction_repo: PredictionRepository,
    ) -> None: ...

    async def search(self, question: str, limit: int = 10) -> QueryResult:
        vec = await self._embedder.embed(question)
        matches = await self._vector_store.search_similar(vec, limit=limit)
        by_id = {p.id: p for p in await self._prediction_repo.get_by_ids([m.prediction_id for m in matches])}
        results = [
            RetrievedPrediction(prediction=by_id[m.prediction_id], distance=m.distance, rank=i + 1)
            for i, m in enumerate(matches)
            if m.prediction_id in by_id
        ]
        return QueryResult(query=question, results=results)
```
Типізовані Protocol-залежності (CLAUDE.md:82). Чистий ранжир, без порога.

### 4. `POST /query` (`app.py`) — NEW
Request/response — Pydantic. `limit` обмежений (1..50) щоб не зловживали.
```python
class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)

@app.post("/query", response_model=QueryResult)
async def query(req: QueryRequest, request: Request) -> QueryResult:
    qo = getattr(request.app.state, "query_orchestrator", None)
    if qo is None:
        raise HTTPException(503, "query orchestrator not initialized")
    try:
        return await qo.search(req.question, req.limit)
    except Exception as exc:
        logger.exception("query failed")
        raise HTTPException(500, f"query failure: {type(exc).__name__}")
```

### 5. `factory.build_query_orchestrator(settings, stack)` — NEW
engine + `PostgresPredictionRepository` + `PostgresVectorStore` + `EmbeddingClient`. **Без Telegram**
(query його не потребує). `EmbeddingClient` будується завжди (ембедить запит незалежно від
`embeddings_enabled`). `lifespan` будує його поряд з ingestion-оркестратором і кладе на
`app.state.query_orchestrator`.

## Потік даних та обробка помилок

| Ситуація | Поведінка |
|----------|-----------|
| Порожнє `question` | 422 (Pydantic `min_length=1`) — до оркестратора не доходить |
| Нічого не знайдено (порожній корпус / 0 матчів) | 200, `results: []` — це не помилка |
| `get_by_ids` не знайшов id (рейс із видаленням) | мовчки пропустити той запис, решта — у відповіді |
| Збій ембедера / БД | 500, `logger.exception(...)`, як `/ingest/run` |

Логування — `logger` (CLAUDE.md:92, без `print()`); лог-рядок INFO: `query: limit=%d results=%d`
(без тексту запиту як payload — CLAUDE.md:106; за потреби — `DEBUG`).

## Тестування

**Unit (in-memory fakes, без БД/мережі):**
- `QueryOrchestrator.search`: wiring (embed→search→get_by_ids), порядок результатів = порядок
  matches, коректні `rank` (1-based) і `distance`; фільтр відсутніх id.
- `get_by_ids`: повертає у порядку вхідних `ids`; пропускає відсутні.
- `search_similar` (fake + контракт): повертає `list[VectorMatch]`.
- `POST /query`: 422 на порожнє питання; 200 з порожнім `results`; happy-path (через ASGI з
  fake-оркестратором на `app.state`).

**Інтеграційно (опційно, real Postgres + EmbeddingClient, як `integration_smoke`):**
- реальний запит → осмислені прогнози у відповіді; перевірка, що endpoint віддає валідний JSON.

## Скоуп

**In:** `VectorMatch`/`RetrievedPrediction`/`QueryResult`, scored `search_similar`, `get_by_ids`,
`QueryOrchestrator`, `POST /query`, `build_query_orchestrator`, unit + smoke.

**Out (deferred):**
- **Генерація відповіді** (LLM, citation, refusal, faithfulness-eval) — v1.5, сяде як `answer()` зверху.
- **Метадані-фільтри / hybrid search** (status/person/date/RRF) — Phase 2.
- **Поріг релевантності / refusal-cutoff** — v1.5 (тюнінг по gold).
- **Telegram-бот** — окремий фронтенд-цикл, споживає `QueryResult` або згенеровану відповідь.
- **Кешування, query-transform, multi-turn** — post-MVP.

## Очікуваний результат

Робочий `POST /query`, що на питання UA повертає top-k прогнозів із `distance`+`rank` (детерміновано,
без галюцинацій), і `QueryOrchestrator.search()` як чистий шов, на який у v1.5 сяде генерація.
