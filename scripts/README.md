# `scripts/` — operational scripts and data

Python-скрипти живуть плоско в `scripts/` (через cross-imports). Дані та артефакти прогонів згруповані по сценаріях у підкаталогах.

## Сценарії

### 1. Telegram-збір → переселено в `src/prophet_checker/sources/telegram.py`

Логіка переселена в production-модуль (Task 21, 2026-04-29).
Виклик тепер відбувається через `IngestionOrchestrator` (Task 15, planned)
а не через CLI-скрипт.

Історичні artifacts (від попередніх script-runs) залишаються в `data/`:

| Файл | Опис |
|------|------|
| `tg_session.session` | Telethon auth artifact (gitignored) |
| `data/sample_posts.json` | Канонічний multi-author датасет для evals (1049 постів) |
| `data/sample_posts_100.json` | Малий sample для швидких тестів |
| `data/arestovich/all.json` | Сирий dump каналу Арестовича від попереднього script-run |
| `data/zdanov/1.json` | Сирий dump каналу Жданова |

### 2. Gold-лейбли → `data/gold_labels.json`

Канонічна gold-розмітка для evals. 130 постів (97 Арестович + 16 Подоляк + 17 інших), кожен з `has_prediction: bool`.

| Файл | Опис |
|------|------|
| `data/gold_labels.json` | Поточна gold (Task 12, 130 entries) |
| `data/annotation_sample.json` | Раніша анотаційна вибірка |
| `data/_legacy/` | Ранні мануальні експерименти (predictions_*.txt, predictions_manual.json — порожні / архівні) |

### 3. Detection eval (Task 13) → `outputs/detection_eval/`

YES/NO-класифікація: чи є взагалі передбачення в пості.

```bash
.venv/bin/python scripts/evaluate_detection.py --model all-primary
```

| Файл | Опис |
|------|------|
| `evaluate_detection.py` | CLI: 5 моделей × 2 промптові версії, F1/precision/recall |
| `outputs/detection_eval/detection_results_<provider>_<model>.json` | Результати v2 (поточний промпт) |
| `outputs/detection_eval/detection_results_<...>_v1_baseline.json` | Результати v1 (baseline промпт) |

Переможець (Task 13): **Gemini 3.1 Flash Lite Preview** з F1 = 0.848.

### 4. Extraction quality eval (Task 13.5) → `outputs/extraction_eval/`

LLM-as-judge для якості витягнутих claims.

```bash
.venv/bin/python scripts/extraction_quality_eval.py --gold-only
```

| Файл | Опис |
|------|------|
| `extraction_quality_eval.py` | 3-stage pipeline: extraction → Opus judge → aggregate |
| `extraction_judge_prompts.py` | Judge SYSTEM + USER templates, 6-value verdict enum |
| `outputs/extraction_eval/extraction_outputs.json` | Stage 1 artifact: extractor → post → claims[] |
| `outputs/extraction_eval/extraction_judgements.json` | Stage 2 artifact: per-claim verdicts + missed_predictions |
| `outputs/extraction_eval/extraction_eval_report.json` | Stage 3 artifact: aggregated metrics |
| `outputs/extraction_eval/gemini_missed_predictions.json` | Аналітичний дамп missed_predictions з прогону |

Переможець (Task 13.5): **Gemini 3.1 Pro Preview** за `avg_quality_score` = 2.30 (precision 65 %), але **Flash Lite** виграє за recall (73 % vs 60 %) і коштує в **33×** менше.

## Cross-imports

`extraction_quality_eval.py` імпортує з `evaluate_detection.py`:
- `CONCURRENCY_OVERRIDES` — per-model concurrency limits
- `MIN_CALL_INTERVAL_SECONDS` — per-model rate-limit throttle
- `PROVIDER_API_KEY_ENV` — provider → env-var mapping
- `_default_extractor_factory` — LiteLLM-backed extractor builder

Тому скрипти лежать в одній папці (Python виявляє один з одного через `sys.path[0]`).

## Виконання тестів

```bash
.venv/bin/python -m pytest tests/ -q
```

88 тестів покривають evaluate_detection (60) + extraction_quality_eval (28).

## Конфіг

`.env` у корені проекту: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY, GROQ_API_KEY, TELEGRAM_API_ID, TELEGRAM_API_HASH.

`extraction_quality_eval.py` робить `load_dotenv(override=True)` автоматично — env-файл не треба експортувати в shell.
