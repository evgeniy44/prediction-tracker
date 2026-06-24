# Query Serving (RAG retrieval-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /query` що на питання UA повертає top-k релевантних прогнозів із `distance`+`rank` (retrieval-only, без генерації, детерміновано).

**Architecture:** Новий пакет `query/` з `QueryOrchestrator` (дзеркалить Ingestion/Verification-оркестратори): embed query → `VectorStore.search_similar` (тепер зі score) → `PredictionRepository.get_by_ids` → `QueryResult`. Композиція у `factory.build_query_orchestrator`, endpoint у `app.py` через `lifespan`. Усі межі — іменовані Pydantic-моделі.

**Tech Stack:** Python 3.14, async SQLAlchemy + pgvector, FastAPI, LiteLLM (`EmbeddingClient`), pytest (`asyncio_mode=auto`), httpx ASGITransport для endpoint-тестів, ruff.

**Spec:** [`2026-06-22-query-serving-design.md`](2026-06-22-query-serving-design.md)

**Без міграцій:** зміни не торкаються `models/db.py` (колонка `embedding` уже існує).

---

## File Structure

```
src/prophet_checker/
  models/domain.py        # + VectorMatch, RetrievedPrediction, QueryResult
  storage/interfaces.py   # search_similar → list[VectorMatch]; + PredictionRepository.get_by_ids
  storage/postgres.py     # impl search_similar (зі score) + get_by_ids
  query/__init__.py       # NEW — експорт QueryOrchestrator
  query/orchestrator.py   # NEW — QueryOrchestrator.search()
  factory.py              # + build_query_orchestrator
  app.py                  # + QueryRequest, POST /query, lifespan wiring
tests/
  test_storage_interfaces.py  # update search_similar test; + get_by_ids test
  test_query_orchestrator.py  # NEW
  test_app_endpoints.py       # + /query tests
```

Конвенції: типізовані Pydantic-межі (CLAUDE.md:80); типізовані Protocol-залежності (CLAUDE.md:82);
edit-in-place (CLAUDE.md:86); `logger`, без `print()` у `src/` (CLAUDE.md:92); коміти укр. conventional.

---

### Task 1: Доменні моделі query-результату

**Files:**
- Modify: `src/prophet_checker/models/domain.py`
- Test: `tests/test_query_models.py`

- [ ] **Step 1: Написати падаючий тест**

```python
# tests/test_query_models.py
from datetime import date

from prophet_checker.models.domain import (
    Prediction,
    QueryResult,
    RetrievedPrediction,
    VectorMatch,
)


def test_vector_match_fields():
    m = VectorMatch(prediction_id="p1", distance=0.12)
    assert m.prediction_id == "p1"
    assert m.distance == 0.12


def test_query_result_nests_retrieved_predictions():
    pred = Prediction(
        id="p1", document_id="d", person_id="x", claim_text="c", prediction_date=date(2024, 1, 1)
    )
    qr = QueryResult(query="q", results=[RetrievedPrediction(prediction=pred, distance=0.2, rank=1)])
    assert qr.query == "q"
    assert qr.results[0].prediction.id == "p1"
    assert qr.results[0].rank == 1
    assert qr.results[0].distance == 0.2
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_query_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'VectorMatch'`

- [ ] **Step 3: Додати моделі в кінець `models/domain.py`**

```python
class VectorMatch(BaseModel):
    prediction_id: str
    distance: float  # cosine-distance: менше = ближче


class RetrievedPrediction(BaseModel):
    prediction: Prediction
    distance: float
    rank: int  # 1-based, порядок за схожістю


class QueryResult(BaseModel):
    query: str
    results: list[RetrievedPrediction]
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_query_models.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check src/prophet_checker/models/domain.py tests/test_query_models.py
.venv/bin/ruff format src/prophet_checker/models/domain.py tests/test_query_models.py
git add src/prophet_checker/models/domain.py tests/test_query_models.py
git commit -m "feat(query): доменні моделі VectorMatch/RetrievedPrediction/QueryResult"
```

---

### Task 2: `search_similar` повертає `list[VectorMatch]`

**Files:**
- Modify: `src/prophet_checker/storage/interfaces.py`
- Modify: `src/prophet_checker/storage/postgres.py`
- Modify: `tests/fakes.py`
- Test: `tests/test_storage_interfaces.py` (оновити наявний `test_vector_store_search`)

- [ ] **Step 1: Оновити тест під новий контракт**

Замінити наявний `test_vector_store_search` (рядки 82–87) на:

```python
async def test_vector_store_search():
    store = FakeVectorStore()
    await store.store_embedding("p1", [0.1, 0.2, 0.3])
    await store.store_embedding("p2", [0.4, 0.5, 0.6])
    results = await store.search_similar([0.1, 0.2, 0.3], limit=1)
    assert len(results) == 1
    assert results[0].prediction_id == "p1"
    assert isinstance(results[0].distance, float)
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_storage_interfaces.py::test_vector_store_search -q`
Expected: FAIL — `AttributeError: 'str' object has no attribute 'prediction_id'`

- [ ] **Step 3: Оновити Protocol** (`storage/interfaces.py`)

У блоці `from prophet_checker.models.domain import (...)` додати `VectorMatch`. Змінити метод
`VectorStore.search_similar`:

```python
class VectorStore(Protocol):
    async def store_embedding(self, prediction_id: str, embedding: list[float]) -> None: ...
    async def search_similar(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[VectorMatch]: ...
```

- [ ] **Step 4: Оновити фейк** (`tests/fakes.py`)

Додати `VectorMatch` до імпорту з `models.domain`. Замінити `FakeVectorStore.search_similar`:

```python
    async def search_similar(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[VectorMatch]:
        return [
            VectorMatch(prediction_id=pid, distance=float(i))
            for i, (pid, _) in enumerate(self._entries[:limit])
        ]
```

- [ ] **Step 5: Оновити Postgres-impl** (`storage/postgres.py`)

Додати `VectorMatch` до імпорту з `models.domain`. Замінити тіло `PostgresVectorStore.search_similar`:

```python
    async def search_similar(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[VectorMatch]:
        async with self._session_factory() as session:
            dist = PredictionDB.embedding.cosine_distance(query_embedding)
            stmt = select(PredictionDB.id, dist.label("distance")).order_by(dist).limit(limit)
            result = await session.execute(stmt)
            return [VectorMatch(prediction_id=r[0], distance=r[1]) for r in result.all()]
```

- [ ] **Step 6: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_storage_interfaces.py -q`
Expected: PASS

- [ ] **Step 7: Lint + commit**

```bash
.venv/bin/ruff check src/prophet_checker/storage/ tests/fakes.py tests/test_storage_interfaces.py
.venv/bin/ruff format src/prophet_checker/storage/ tests/fakes.py tests/test_storage_interfaces.py
git add src/prophet_checker/storage/ tests/fakes.py tests/test_storage_interfaces.py
git commit -m "feat(storage): search_similar повертає VectorMatch (id + distance)"
```

---

### Task 3: `PredictionRepository.get_by_ids`

**Files:**
- Modify: `src/prophet_checker/storage/interfaces.py`
- Modify: `src/prophet_checker/storage/postgres.py`
- Modify: `tests/fakes.py`
- Test: `tests/test_storage_interfaces.py`

- [ ] **Step 1: Написати падаючий тест** (додати в `tests/test_storage_interfaces.py`)

```python
async def test_get_by_ids_preserves_order_and_skips_missing():
    repo = FakePredictionRepo()
    await repo.save(
        Prediction(id="a", document_id="d", person_id="1", claim_text="A", prediction_date=date(2023, 1, 1))
    )
    await repo.save(
        Prediction(id="b", document_id="d", person_id="1", claim_text="B", prediction_date=date(2023, 1, 1))
    )
    got = await repo.get_by_ids(["b", "missing", "a"])
    assert [p.id for p in got] == ["b", "a"]
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_storage_interfaces.py::test_get_by_ids_preserves_order_and_skips_missing -q`
Expected: FAIL — `AttributeError: 'FakePredictionRepo' object has no attribute 'get_by_ids'`

- [ ] **Step 3: Додати в Protocol** (`storage/interfaces.py`, у `PredictionRepository`)

```python
    async def get_by_ids(self, ids: list[str]) -> list[Prediction]: ...
```

- [ ] **Step 4: Додати у фейк** (`tests/fakes.py`, у `FakePredictionRepo`)

```python
    async def get_by_ids(self, ids: list[str]) -> list[Prediction]:
        by_id = {p.id: p for p in self._predictions}
        return [by_id[i] for i in ids if i in by_id]
```

- [ ] **Step 5: Додати Postgres-impl** (`storage/postgres.py`, у `PostgresPredictionRepository`)

```python
    async def get_by_ids(self, ids: list[str]) -> list[Prediction]:
        if not ids:
            return []
        async with self._session_factory() as session:
            stmt = select(PredictionDB).where(PredictionDB.id.in_(ids))
            result = await session.execute(stmt)
            by_id = {row.id: prediction_db_to_domain(row) for row in result.scalars().all()}
        return [by_id[i] for i in ids if i in by_id]
```

- [ ] **Step 6: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_storage_interfaces.py -q`
Expected: PASS

- [ ] **Step 7: Lint + commit**

```bash
.venv/bin/ruff check src/prophet_checker/storage/ tests/fakes.py tests/test_storage_interfaces.py
.venv/bin/ruff format src/prophet_checker/storage/ tests/fakes.py tests/test_storage_interfaces.py
git add src/prophet_checker/storage/ tests/fakes.py tests/test_storage_interfaces.py
git commit -m "feat(storage): PredictionRepository.get_by_ids (order-preserving)"
```

---

### Task 4: `QueryOrchestrator.search`

**Files:**
- Create: `src/prophet_checker/query/__init__.py`
- Create: `src/prophet_checker/query/orchestrator.py`
- Test: `tests/test_query_orchestrator.py`

- [ ] **Step 1: Написати падаючий тест**

```python
# tests/test_query_orchestrator.py
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from fakes import FakePredictionRepo, FakeVectorStore

from prophet_checker.models.domain import Prediction
from prophet_checker.query.orchestrator import QueryOrchestrator


def _embedder():
    e = MagicMock()
    e.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return e


async def test_search_ranks_and_orders_results():
    store = FakeVectorStore()
    await store.store_embedding("p1", [0.1, 0.1, 0.1])
    await store.store_embedding("p2", [0.2, 0.2, 0.2])
    repo = FakePredictionRepo()
    for pid in ("p1", "p2"):
        await repo.save(
            Prediction(id=pid, document_id="d", person_id="x", claim_text=pid, prediction_date=date(2024, 1, 1))
        )
    orch = QueryOrchestrator(_embedder(), store, repo)

    result = await orch.search("питання", limit=10)

    assert result.query == "питання"
    assert [r.prediction.id for r in result.results] == ["p1", "p2"]
    assert [r.rank for r in result.results] == [1, 2]
    assert result.results[0].distance == 0.0  # FakeVectorStore: distance = індекс


async def test_search_drops_matches_without_prediction():
    store = FakeVectorStore()
    await store.store_embedding("ghost", [0.1, 0.1, 0.1])  # match є, прогнозу немає
    orch = QueryOrchestrator(_embedder(), store, FakePredictionRepo())
    result = await orch.search("q")
    assert result.results == []


async def test_search_empty_corpus_returns_empty():
    orch = QueryOrchestrator(_embedder(), FakeVectorStore(), FakePredictionRepo())
    result = await orch.search("q")
    assert result.results == []
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_query_orchestrator.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prophet_checker.query'`

- [ ] **Step 3: Створити пакет + оркестратор**

```python
# src/prophet_checker/query/__init__.py
from prophet_checker.query.orchestrator import QueryOrchestrator

__all__ = ["QueryOrchestrator"]
```

```python
# src/prophet_checker/query/orchestrator.py
from __future__ import annotations

from prophet_checker.llm import EmbeddingClient
from prophet_checker.models.domain import QueryResult, RetrievedPrediction
from prophet_checker.storage.interfaces import PredictionRepository, VectorStore


class QueryOrchestrator:
    def __init__(
        self,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
        prediction_repo: PredictionRepository,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._prediction_repo = prediction_repo

    async def search(self, question: str, limit: int = 10) -> QueryResult:
        embedding = await self._embedder.embed(question)
        matches = await self._vector_store.search_similar(embedding, limit=limit)
        by_id = {
            p.id: p
            for p in await self._prediction_repo.get_by_ids([m.prediction_id for m in matches])
        }
        results = [
            RetrievedPrediction(prediction=by_id[m.prediction_id], distance=m.distance, rank=rank)
            for rank, m in enumerate(matches, start=1)
            if m.prediction_id in by_id
        ]
        return QueryResult(query=question, results=results)
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_query_orchestrator.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check src/prophet_checker/query/ tests/test_query_orchestrator.py
.venv/bin/ruff format src/prophet_checker/query/ tests/test_query_orchestrator.py
git add src/prophet_checker/query/ tests/test_query_orchestrator.py
git commit -m "feat(query): QueryOrchestrator.search — embed→search→fetch→ранжування"
```

---

### Task 5: `factory.build_query_orchestrator`

**Files:**
- Modify: `src/prophet_checker/factory.py`

(Без unit-тесту — як `build_orchestrator`/`build_verification_orchestrator`, будує реальний engine;
покривається endpoint-тестами Task 6, що інжектять фейк, та integration-перевіркою Task 7.)

- [ ] **Step 1: Додати імпорти** (`factory.py`)

До наявного `from prophet_checker.storage.postgres import (...)` додати `PostgresVectorStore`.
Додати:

```python
from prophet_checker.query import QueryOrchestrator
```

- [ ] **Step 2: Додати білдер** (у кінець `factory.py`)

```python
async def build_query_orchestrator(
    settings: Settings, stack: AsyncExitStack
) -> QueryOrchestrator:
    engine = create_async_engine(settings.database_url, echo=False)
    stack.push_async_callback(engine.dispose)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    prediction_repo = PostgresPredictionRepository(session_factory)
    vector_store = PostgresVectorStore(session_factory)
    embedder = EmbeddingClient(model=settings.embedding_model, api_key=settings.openai_api_key)
    return QueryOrchestrator(embedder, vector_store, prediction_repo)
```

- [ ] **Step 3: Перевірити імпорт + lint**

Run: `.venv/bin/python -c "import prophet_checker.factory"`
Expected: без помилок

```bash
.venv/bin/ruff check src/prophet_checker/factory.py
.venv/bin/ruff format src/prophet_checker/factory.py
```

- [ ] **Step 4: Commit**

```bash
git add src/prophet_checker/factory.py
git commit -m "feat(query): build_query_orchestrator (без Telegram, власний embedder)"
```

---

### Task 6: `POST /query` endpoint + lifespan wiring

**Files:**
- Modify: `src/prophet_checker/app.py`
- Test: `tests/test_app_endpoints.py`

- [ ] **Step 1: Написати падаючі тести** (додати в `tests/test_app_endpoints.py`)

До імпорту `from datetime import UTC, datetime` додати `date`. Додати:

```python
@pytest.fixture(autouse=True)
def _clear_query_orchestrator_state():
    yield
    if hasattr(app.state, "query_orchestrator"):
        delattr(app.state, "query_orchestrator")


async def test_query_returns_results():
    from prophet_checker.models.domain import Prediction, QueryResult, RetrievedPrediction

    qo = MagicMock()
    pred = Prediction(
        id="p1", document_id="d", person_id="x", claim_text="c", prediction_date=date(2024, 1, 1)
    )
    qo.search = AsyncMock(
        return_value=QueryResult(
            query="q", results=[RetrievedPrediction(prediction=pred, distance=0.1, rank=1)]
        )
    )
    app.state.query_orchestrator = qo

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/query", json={"question": "q", "limit": 5})

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "q"
    assert body["results"][0]["prediction"]["id"] == "p1"
    assert body["results"][0]["rank"] == 1


async def test_query_422_on_empty_question():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/query", json={"question": "", "limit": 5})
    assert resp.status_code == 422


async def test_query_503_when_not_initialized():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/query", json={"question": "q"})
    assert resp.status_code == 503
```

- [ ] **Step 2: Запустити — переконатись, що падає**

Run: `.venv/bin/python -m pytest tests/test_app_endpoints.py::test_query_503_when_not_initialized -q`
Expected: FAIL — 404 (endpoint ще не існує), не 503

- [ ] **Step 3: Оновити `app.py`**

Додати імпорти зверху:

```python
from pydantic import BaseModel, Field

from prophet_checker.factory import build_orchestrator, build_query_orchestrator
from prophet_checker.models.domain import QueryResult
```

(`from prophet_checker.factory import build_orchestrator` уже є — замінити на рядок із двома іменами.)

У `lifespan`, після `app.state.orchestrator = orchestrator`, додати:

```python
        app.state.query_orchestrator = await build_query_orchestrator(settings, stack)
```

Додати модель запиту й endpoint (після `run_ingestion`):

```python
class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


@app.post("/query", response_model=QueryResult)
async def query(req: QueryRequest, request: Request) -> QueryResult:
    query_orchestrator = getattr(request.app.state, "query_orchestrator", None)
    if query_orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="query orchestrator not initialized — server is starting up or shutting down",
        )
    try:
        return await query_orchestrator.search(req.question, req.limit)
    except Exception as exc:
        logger.exception("query failed")
        raise HTTPException(status_code=500, detail=f"query failure: {type(exc).__name__}")
```

- [ ] **Step 4: Запустити — переконатись, що проходить**

Run: `.venv/bin/python -m pytest tests/test_app_endpoints.py -q`
Expected: PASS (усі — наявні ingest + 3 нові query)

- [ ] **Step 5: Lint + повна сюїта**

```bash
.venv/bin/ruff check src/prophet_checker/app.py tests/test_app_endpoints.py
.venv/bin/ruff format src/prophet_checker/app.py tests/test_app_endpoints.py
.venv/bin/python -m pytest tests/ -q
```
Expected: уся сюїта PASS

- [ ] **Step 6: Commit**

```bash
git add src/prophet_checker/app.py tests/test_app_endpoints.py
git commit -m "feat(query): POST /query endpoint + lifespan wiring"
```

---

### Task 7: Ручна інтеграційна перевірка (real Postgres + LLM, опційно)

**Files:** немає (ручні кроки)

**Передумова:** `docker compose up -d`; `.venv/bin/alembic upgrade head`; у БД є прогнози з
ембедингами (прогнати `scripts/ingestion/backfill_embeddings.py`); `OPENAI_API_KEY` у `.env`.

- [ ] **Step 1: Запустити застосунок**

Run: `.venv/bin/python -m prophet_checker`
Expected: uvicorn на `127.0.0.1:8000`, `curl localhost:8000/health` → `{"status":"ok"}`

- [ ] **Step 2: Запит до /query**

Run:
```bash
curl -s -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question": "що казали про завершення війни", "limit": 5}' | python3 -m json.tool
```
Expected: JSON `{"query": ..., "results": [{"prediction": {...}, "distance": <float>, "rank": 1}, ...]}`
з осмисленими (тематично близькими) прогнозами, відсортованими за `rank`.

---

## Follow-ups (поза цим планом)

- **v1.5 генерація:** `answer(QueryResult) → str` через `build_rag_prompt` + `RAG_SYSTEM` (вже є);
  потребує citation-контракту, refusal-політики, faithfulness-eval (LLM-as-judge).
- **Phase 2:** метадані-фільтри/hybrid (status/person/date/RRF), поріг релевантності (тюнінг по gold).
- **Telegram-бот:** окремий фронтенд, споживає `QueryResult` або згенеровану відповідь.
