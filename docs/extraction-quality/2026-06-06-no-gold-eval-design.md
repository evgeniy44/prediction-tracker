# Extraction-quality eval без gold — Design

**Дата:** 2026-06-06
**Статус:** approved (очікує план)
**Трек:** extraction-quality
**Файл:** `scripts/extraction/extraction_quality_eval.py`

## Мета

Дозволити запускати extraction-quality eval (LLM-as-judge) на **довільних постах** без `gold_labels.json`, отримуючи judge-only метрики якості claim-ів. Без gold губиться лише recall-сторона (відносно істини), judge-якість претензій лишається.

## Що залежить від gold (і що ні)

- **Gold-залежне:** `missed_rate` (знаменник = к-сть gold-YES постів), `gold_agreement` матриця, фільтр `--gold-only`.
- **Judge-only (працює без gold):** `avg_quality_score`, `hallucination_rate`, `verdict_distribution`, `total_claims`, `invalid_verdict_count`, `parse_error_count`, `missed_predictions_count` (суддя сам репортить пропущене).

CLI-таблиця підсумку показує лише `avg_score/hall_rate/missed-count/claims` — gold-полів не виводить, тож вивід не ламається.

## Прийняті рішення

1. **null** для gold-залежних полів (`missed_rate`, `gold_agreement`), коли gold відсутній (не нулі, не omit — стабільна схема, явне «не обчислено»).
2. **Прапорець `--no-gold`** (backward-compatible): `--gold` лишає дефолт `gold_labels.json`; `--no-gold` явно вимикає gold. `--no-gold` + `--gold-only` → помилка (взаємовиключні). Наявні запуски не змінюються.

## Зміни

### A — `aggregate_metrics(judgements, gold_labels=None)`
`gold_labels` стає опціональним. `no_gold = not gold_labels` (None або `[]`):
```python
no_gold = not gold_labels
gold_index = {} if no_gold else {g["id"]: g["has_prediction"] for g in gold_labels}
...
"missed_rate": None if no_gold else missed_rate,
"gold_agreement": None if no_gold else { ...існуюча матриця... },
```
Решта обчислень без змін. With-gold вивід ідентичний поточному.

### B — `run_stage3_aggregate(..., gold_labels_path: Path | None = None)`
`gold_labels_path is None` → `gold_labels = None` (файл не читаємо), інакше читаємо як зараз. Метадані `source_gold` = `str(path)` або `None`.

### C — `_main_async` + `_build_arg_parser`
- Новий `--no-gold` (`store_true`).
- Валідація: `args.no_gold and args.gold_only` → `parser.error("--no-gold та --gold-only взаємовиключні")`.
- Stage 3: `gold_labels_path = None if args.no_gold else Path(args.gold)`.

### D — module docstring
Додати `--no-gold` у секцію «Вхід»; зазначити: без gold `missed_rate`/`gold_agreement` = `null`.

## Тести (no-gold шлях)

- `aggregate_metrics(judgements=<fixture>, gold_labels=None)` → `missed_rate is None`, `gold_agreement is None`; `avg_quality_score`/`hallucination_rate`/`missed_predictions_count` обчислені правильно.
- `aggregate_metrics(..., gold_labels=[])` → те саме (порожній gold = no-gold).
- `_build_arg_parser()` має `--no-gold`.

## Поза скоупом

- Stage 1/2 (extraction/judge) не змінюються (gold там лише у `--gold-only`, який несумісний з `--no-gold`).
- Жодних нових метрик-замінників recall без gold.
- Зміни prompts/extractor/схеми БД — ні.

## Обмеження

NO inline comments; module-header docstring дозволений. `.venv/bin/python`. Українські коміти. Наявні 207 тестів зелені; +3 → 210.
