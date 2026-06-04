# Optional embeddings в ingestion — Design

**Дата:** 2026-06-03
**Статус:** Spec ready
**Мета:** Дозволити ingestion працювати **без OpenAI-ключа**, пропускаючи embedding клеймів.

---

## Контекст

`IngestionOrchestrator._process_channel` для кожного прогнозу робить
`p.embedding = await self._embedder.embed(p.claim_text)` перед save. Embedder — це
`EmbeddingClient` (OpenAI), будується у `factory.build_orchestrator` з `settings.openai_api_key`.
Колонка `predictions.embedding` — `Vector(1536), nullable=True`. Verifier embeddings не використовує;
вони потрібні лише для RAG. Тож новий `run_ingestion.py` / real-DB smoke зараз вимагають OpenAI лише
заради наповнення прогнозів.

## Дизайн: config-flag + опційний embedder

- **`config.py`** — нове поле `embeddings_enabled: bool = True` (default зберігає поточну поведінку).
- **`factory.build_orchestrator`** — будувати `EmbeddingClient` **лише** якщо `settings.embeddings_enabled`,
  інакше `embedder = None`. Коли вимкнено, `EmbeddingClient` не створюється → OpenAI-ключ не потрібен.
- **`IngestionOrchestrator`** — `embedder` типізувати як опційний; ембед-луп під guard:
  `if self._embedder is not None: for p in predictions: p.embedding = await self._embedder.embed(...)`.
  Коли `None` — `p.embedding` лишається `None` і зберігається (колонка nullable).
- **`scripts/run_ingestion.py`** — прапорець `--no-embeddings` → `Settings(embeddings_enabled=False)`
  (перекриває `.env`), щоб запускати gemini-only ad-hoc без редагування конфігу.

**Чому не null-object embedder / не bool у orchestrator:** None-check — один рядок; окремий
`NullEmbedder`-клас або дублюючий bool додають код без виграшу.

## Компоненти та файли

| File | Зміна |
|---|---|
| `src/prophet_checker/config.py` | `embeddings_enabled: bool = True` |
| `src/prophet_checker/factory.py` | будувати embedder лише якщо enabled, інакше `None` |
| `src/prophet_checker/ingestion/orchestrator.py` | `embedder` опційний; guard ембед-лупу |
| `scripts/run_ingestion.py` | `--no-embeddings` → `Settings(embeddings_enabled=False)` |
| `tests/test_ingestion_orchestrator.py` | embedder=None → embed не викликається, embedding=None |
| `docs/verification-track/20-verification-orchestrator/real-db-smoke.md` | нотатка про `--no-embeddings` (OPENAI не потрібен) |

## Потік даних (вимкнено)

`factory` → `embedder=None` → orchestrator пропускає embed → прогнози зберігаються з `embedding=NULL`
(не RAG-searchable — задокументований tradeoff).

## Тестування

`tests/test_ingestion_orchestrator.py`: новий тест — orchestrator з `embedder=None`, run_cycle на пості
з прогнозами → embed жодного разу не викликано (embedder=None, нема що викликати) + збережений прогноз
має `embedding is None`. Наявні тести (з fake-embedder) — без змін.

## Поза скоупом

- Зміни схеми БД (колонка вже nullable).
- Зміни `app.py` (йде через factory).
- Поведінка RAG-пошуку на null-embeddings (ці прогнози просто не знаходяться) — окремо, якщо знадобиться.
