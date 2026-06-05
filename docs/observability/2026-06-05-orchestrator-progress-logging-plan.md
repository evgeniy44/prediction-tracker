# Періодичне логування прогресу оркестраторів — Implementation Plan

> **For agentic workers:** Виконання inline в цій сесії (дрібний скоуп, без тестів за рішенням користувача). Кроки — checkbox (`- [ ]`).

**Goal:** Емітити `logger.info` кожні `log_every` записів + підсумок наприкінці циклу в обох оркестраторах.

**Architecture:** Модульний логер на кожен файл + параметр конструктора `log_every: int = 50`. Прогрес-рядок усередині гарячого циклу, підсумковий рядок перед `return`.

**Tech Stack:** Python 3.12, stdlib `logging`.

**Обмеження:** NO docstrings, NO inline comments. Команди через `.venv/bin/python`. Working dir `/Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker`. Без тестів. Коміти українською.

---

### Task 1: Логування в `IngestionOrchestrator`

**Files:**
- Modify: `src/prophet_checker/ingestion/orchestrator.py`

- [ ] **Step 1: Додати модульний логер**

У шапці файлу, після рядка `from __future__ import annotations` додати `import logging`, а після блоку імпортів (перед `class IngestionOrchestrator`) додати:

```python
logger = logging.getLogger(__name__)
```

- [ ] **Step 2: Параметр конструктора**

В `__init__` додати останнім параметром `log_every: int = 50` і присвоєння в тілі:

```python
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        source_repo: SourceRepository,
        prediction_repo: PredictionRepository,
        extractor,
        embedder,
        sources: Mapping[SourceType, Source],
        log_every: int = 50,
    ) -> None:
        self._session_factory = session_factory
        self._source_repo = source_repo
        self._prediction_repo = prediction_repo
        self._extractor = extractor
        self._embedder = embedder
        self._sources = sources
        self._log_every = log_every
```

- [ ] **Step 3: Прогрес-рядок усередині циклу**

В `_process_channel`, всередині `async for`, після `report.cursor_advanced_to = raw_doc.published_at` (останній рядок тіла ітерації, всередині `try`):

```python
                report.cursor_advanced_to = raw_doc.published_at
                if report.posts_seen % self._log_every == 0:
                    logger.info(
                        "ingestion %s: seen=%d with_predictions=%d extracted=%d",
                        ps.id, report.posts_seen, report.posts_with_predictions, report.predictions_extracted,
                    )
```

- [ ] **Step 4: Підсумковий рядок**

Перед фінальним `return report` (поза `try/except`, наприкінці `_process_channel`):

```python
        except Exception as exc:
            report.error = f"halted at step=processing: {exc}"
        logger.info(
            "ingestion %s done: seen=%d with_predictions=%d extracted=%d error=%s",
            ps.id, report.posts_seen, report.posts_with_predictions, report.predictions_extracted, report.error or "-",
        )
        return report
```

- [ ] **Step 5: Перевірка**

Run: `.venv/bin/ruff check src/prophet_checker/ingestion/orchestrator.py`
Expected: All checks passed.

---

### Task 2: Логування в `VerificationOrchestrator`

**Files:**
- Modify: `src/prophet_checker/verification/orchestrator.py`

- [ ] **Step 1: Додати модульний логер**

У шапці файлу, після `from __future__ import annotations` додати `import logging`, а після блоку імпортів (перед `def apply_verification_result`) додати:

```python
logger = logging.getLogger(__name__)
```

- [ ] **Step 2: Параметр конструктора**

```python
    def __init__(self, prediction_repo, verifier, attempt_cap: int = 5, log_every: int = 50) -> None:
        self._prediction_repo = prediction_repo
        self._verifier = verifier
        self._attempt_cap = attempt_cap
        self._log_every = log_every
```

- [ ] **Step 3: enumerate + прогрес-рядок**

Замінити `for p in eligible:` на `for i, p in enumerate(eligible, 1):`. Після `await self._prediction_repo.update(updated)`:

```python
            await self._prediction_repo.update(updated)
            if i % self._log_every == 0:
                logger.info(
                    "verification: %d/%d verified=%d failed=%d",
                    i, len(eligible), report.verified, report.failed,
                )
```

- [ ] **Step 4: Підсумковий рядок**

Після `report.finished_at = datetime.now(UTC)`, перед `return report`:

```python
        report.finished_at = datetime.now(UTC)
        logger.info(
            "verification done: verified=%d failed=%d skipped=%d",
            report.verified, report.failed, report.skipped,
        )
        return report
```

- [ ] **Step 5: Перевірка**

Run: `.venv/bin/ruff check src/prophet_checker/verification/orchestrator.py`
Expected: All checks passed.

---

### Final verification

- [ ] **Step 1: Повний прогон тестів** — наявна поведінка незмінна

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 205 passed.

- [ ] **Step 2: Димовий прогон логування** (опціонально, потребує Postgres+Telegram)

Run: `.venv/bin/python scripts/run_ingestion.py --channel @O_Arestovich_official --limit 5`
Expected: рядок `ingestion ps:@O_Arestovich_official done: seen=... extracted=... error=-` у логах.

- [ ] **Step 3: Коміт**

```bash
git add src/prophet_checker/ingestion/orchestrator.py src/prophet_checker/verification/orchestrator.py docs/observability/
git commit -m "feat(observability): періодичне логування прогресу оркестраторів"
```
