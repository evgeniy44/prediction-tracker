# Task 20 — VerificationOrchestrator (first-pass) — Design

**Дата:** 2026-05-31
**Статус:** Spec ready
**Залежності:** 19.9 (Verifier готовий), 19.7b (model = Flash Lite). Розблоковано.

---

## Мета

Production-orchestrator, що бере **ще не верифіковані** прогнози з БД, проганяє кожен через
`Verifier` (2-call split, Flash Lite — 19.9) і записує результат назад у БД разом з urgency-полями.
Patterned на `IngestionOrchestrator` (coordinator + `run_cycle()` → report).

## Скоуп: лише перший прохід

Верифікуємо кожен прогноз **один раз**. Recheck-луп (повторна перевірка `premature` за
`next_check_at`) — **окремий майбутній таск**. Але urgency-поля (`next_check_at`, `max_horizon`)
ми **записуємо вже зараз** на `premature`-результатах, щоб дані були готові для майбутнього recheck.

**Eligibility** = наявний `PredictionRepository.get_unverified()` (status=UNRESOLVED AND
verified_at IS NULL), відфільтрований по `verify_attempts < attempt_cap`. Нова eligibility-query
НЕ потрібна.

## Архітектура

Новий пакет `verification/` (дзеркалить `ingestion/`):

```
VerificationOrchestrator(session_factory, prediction_repo, verifier, attempt_cap=5)
   └─ async run_cycle(limit=None, today=None) -> VerificationCycleReport
        ├─ candidates = await prediction_repo.get_unverified()
        ├─ eligible = [p for p in candidates if p.verify_attempts < attempt_cap]   # skipped = решта
        ├─ if limit: eligible = eligible[:limit]
        └─ for p in eligible:
             ├─ try:  result = await verifier.verify(claim, situation, dates, today)
             │        updated = apply_verification_result(p, result, now)     # pure
             ├─ except Exception as exc:
             │        updated = apply_verification_error(p, exc, now)         # pure
             └─ await prediction_repo.update(updated)
```

Orchestrator лише координує (pull / loop / per-item try-except). Уся логіка маппінгу
result→`Prediction` — у **чистих** функціях, тестованих без БД/LLM.

## Компоненти та файли

### `src/prophet_checker/verification/orchestrator.py` (новий)
- `VerificationOrchestrator` клас (як вище).
- Чисті module-level функції:
  - `apply_verification_result(prediction: Prediction, result: dict, now: datetime) -> Prediction`
  - `apply_verification_error(prediction: Prediction, exc: Exception, now: datetime) -> Prediction`
  - Обидві повертають оновлену копію через `prediction.model_copy(update=...)` (не мутують).

### `src/prophet_checker/verification/report.py` (новий)
Pydantic, дзеркалить `ingestion/report.py`:
- `VerificationEntry(prediction_id: str, status: str | None = None, error: str | None = None)`
- `VerificationCycleReport(started_at, finished_at=None, verified=0, failed=0, skipped=0, entries=[])`

### `src/prophet_checker/verification/__init__.py` (новий)
Експорт `VerificationOrchestrator`, `VerificationCycleReport`.

### `src/prophet_checker/storage/postgres.py` (модифікація)
`PostgresPredictionRepository.update()` зараз пише лише 5 полів (status, confidence, evidence_url,
evidence_text, verified_at). Розширити, щоб персистити **всі** мутабельні verification-поля:
`prediction_strength`, `prediction_value`, `max_horizon`, `next_check_at`, `verify_attempts`,
`last_verify_error`, `last_verify_error_at` (enum-поля як `.value`, узгоджено з наявним
`domain_to_prediction_db`).

### `src/prophet_checker/factory.py` (модифікація)
`build_verification_orchestrator(settings, stack) -> VerificationOrchestrator` — окремий від
`build_orchestrator` (Telegram НЕ потрібен): engine + session_factory + `PostgresPredictionRepository`
+ Flash Lite `LLMClient` (модель фіксована per 19.7b) + `Verifier`.

### Тригер (CLI)
Тонкий entrypoint `scripts/run_verification_cycle.py`: будує через
`factory.build_verification_orchestrator`, викликає `run_cycle()`, друкує report. Ручний запуск,
**без планувальника** (out of scope).

## Маппінг result → `Prediction`

**Success** (`verify()` повернув dict):
- `status` ← `PredictionStatus(result["status"])`
- `confidence` ← `result["confidence"]`
- `prediction_strength` ← `PredictionStrength(result["prediction_strength"])`
- `prediction_value` ← `PredictionValue(result["prediction_value"])`
- `evidence_text` ← `result.get("evidence")`
- `verified_at` ← `now`
- `verify_attempts` ← `+1`
- `last_verify_error` / `last_verify_error_at` ← `None` (очистити)
- якщо `status == premature`: `next_check_at` ← `date.fromisoformat(result["retry_after"])`,
  `max_horizon` ← `date.fromisoformat(result["max_horizon"])` (якщо є)
- інакше (confirmed/refuted/unresolved — термінальні): `next_check_at` = `None`, `max_horizon` = `None`

**Failure** (`verify()` кинув):
- `verify_attempts` ← `+1`
- `last_verify_error` ← `f"{type(exc).__name__}: {exc}"`
- `last_verify_error_at` ← `now`
- `verified_at` **лишається `None`** → прогноз retry-eligible наступним прогоном
- решта полів незмінні

**Attempt cap:** прогнози з `verify_attempts ≥ attempt_cap` (default 5) пропускаються (не
викликаємо `verify`, рахуються у `skipped`). Захист від retry-forever.

## Обробка помилок

Per-item `try/except` у циклі — одна погана відповідь не блокує решту (на відміну від fail-fast).
`verify()` all-or-nothing (19.9): будь-яка LLM/parse-помилка → failure-шлях вище.

## Тестування

`tests/test_verification_orchestrator.py` (новий):
- `apply_verification_result` — confirmed (verified_at set, status/strength/value/evidence, next_check_at=None, attempts+1, error cleared); premature (next_check_at ← retry_after, max_horizon set).
- `apply_verification_error` — attempts+1, error+timestamp, verified_at=None.
- `run_cycle` зі `FakePredictionRepo` (наявний у `tests/fakes.py`) + stub `Verifier` (MagicMock/AsyncMock): верифікує eligible, оновлює repo, report.verified коректний.
- `run_cycle` skip — прогноз із `verify_attempts ≥ cap` → у `skipped`, не верифікується.
- `run_cycle` failure — stub verifier кидає на одному → `report.failed`, цей verified_at=None, решта ок.

`tests/test_storage_postgres.py` (модифікація): `update()` round-trip нових V2-полів
(узгоджено з наявним підходом postgres-тестів).

## Поза скоупом
- Recheck-луп (`premature` → next_check_at → повторна перевірка до max_horizon) — окремий таск.
- Планувальник/cron.
- Зміни схеми БД/домену (усі поля існують: 19.5 + PredictionValue + 19.8d).
