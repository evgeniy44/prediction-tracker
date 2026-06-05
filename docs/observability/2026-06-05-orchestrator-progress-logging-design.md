# Періодичне логування прогресу оркестраторів — Design

**Дата:** 2026-06-05
**Статус:** approved
**Трек:** observability

## Проблема

Довгі прогони оркестраторів (`IngestionOrchestrator`, `VerificationOrchestrator`) мовчать до самого кінця циклу. На прогоні `run_ingestion --limit 500` або верифікації сотень предікшенів неможливо зрозуміти, що процес живий і на якому він записі. Потрібен сигнал життя — рядок `logger.info` кожні X опрацьованих записів плюс підсумок наприкінці циклу.

## Рішення

Емітимо `logger.info` всередині двох гарячих циклів. Інтервал — параметр конструктора `log_every: int = 50` на обох оркестраторах (симетрично до наявного `attempt_cap` у `VerificationOrchestrator`).

### Чому параметр конструктора

- **vs модульна константа** — параметр тестується/конфігурується без monkeypatch.
- **vs параметр `run_cycle(log_every=)`** — конструктор не чіпає call-site'и (`app.py POST /ingest/run`, скрипти), які викликають `run_cycle()` без аргументів.

Дефолт `50` означає, що наявна поведінка не змінюється: дрібні датасети в існуючих тестах нічого нового не логуватимуть.

## Зміни

### `src/prophet_checker/ingestion/orchestrator.py`

1. Модульний логер: `import logging` + `logger = logging.getLogger(__name__)`.
2. Конструктор: новий параметр `log_every: int = 50` → `self._log_every = log_every`.
3. `_process_channel`, всередині `async for` (наприкінці тіла ітерації, після `report.cursor_advanced_to = ...`):
   ```python
   if report.posts_seen % self._log_every == 0:
       logger.info(
           "ingestion %s: seen=%d with_predictions=%d extracted=%d",
           ps.id, report.posts_seen, report.posts_with_predictions, report.predictions_extracted,
       )
   ```
4. Підсумок наприкінці `_process_channel` (перед фінальним `return report`, поза `try`):
   ```python
   logger.info(
       "ingestion %s done: seen=%d with_predictions=%d extracted=%d error=%s",
       ps.id, report.posts_seen, report.posts_with_predictions, report.predictions_extracted, report.error or "-",
   )
   ```

### `src/prophet_checker/verification/orchestrator.py`

1. Модульний логер (наразі відсутній): `import logging` + `logger = logging.getLogger(__name__)`.
2. Конструктор: новий параметр `log_every: int = 50` → `self._log_every = log_every`.
3. `run_cycle`: `for p in eligible:` → `for i, p in enumerate(eligible, 1):`; після `await self._prediction_repo.update(updated)`:
   ```python
   if i % self._log_every == 0:
       logger.info(
           "verification: %d/%d verified=%d failed=%d",
           i, len(eligible), report.verified, report.failed,
       )
   ```
4. Підсумок перед `return report` (після `report.finished_at = ...`):
   ```python
   logger.info(
       "verification done: verified=%d failed=%d skipped=%d",
       report.verified, report.failed, report.skipped,
   )
   ```

## Формат повідомлень

Машинно-парсабельний `key=value`, без емодзі, рівень `INFO`. Прогрес-рядок дає поточну позицію (`seen=N` / `i/len`), підсумок — фінальні лічильники.

## Поза скоупом

- **Тести** — за рішенням користувача не пишемо (зміна логування-only; дефолт `log_every=50` лишає наявні 205 тестів зеленими).
- Стрей `print(...)` у `sources/telegram.py` — лишаємо як є.
- Конфіг/CLI-прапорці для `log_every` — YAGNI; дефолт у коді достатній.

## Обмеження проєкту

NO docstrings, NO inline comments. Прогон верифікації перевірки: `.venv/bin/python -m pytest tests/ -q` має лишитися 205 passed.
