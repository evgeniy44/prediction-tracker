# Task 19.7b — Verification Model Evaluation

**Status:** draft 2026-05-23
**Task:** 19.7b (multi-LLM verification eval → production model decision for Task 20)
**Prerequisites:** ✅ Task 19.5 (V2 verifier foundations), ✅ Task 19.7a (gold v1, archived), ✅ Task 19.8a/c/d (situation field), ✅ Task 19.8b (fresh gold з situation)
**Downstream:** Task 20 (VerificationOrchestrator використає winner model)

---

## TL;DR

Standalone Python eval script (`scripts/verification_eval.py`) прогонить V2 verification prompt через **9 LLM моделей** проти **32 Arestovich gold predictions** (з situation field). Збирає per-model accuracy + confusion matrices для 3 enum полів (status / strength / value), parser_reject_rate, calibration, cost, latency. Застосовує **4-step decision framework** → винесе `production verifier model = X` для Task 20.

**Per-model output files** (mirrors Task 13 pattern): дозволяє incremental runs, resume на failure, parallel-safe debugging.

**Cost:** ~$1.70 для full sweep. **Wall time:** ~25-40 хв (sequential з throttle).

---

## Architectural decisions

| # | Рішення | Обґрунтування |
|---|---|---|
| Q1 | **9-model full sweep** (cheap + mid + expensive tiers) | Покриває production candidates + quality ceiling baseline. CLI дозволяє підмножину через `--model`. |
| Q2 | **Per-model output files** (one JSON per model) | Incremental runs, resume-safe, smaller diffs, parallel-safe. Mirrors Task 13 (`detection_results_<model>.json`). |
| Q3 | **2-stage pipeline** (RUN → AGGREGATE) | Stage 2 standalone — можна re-compute metrics без re-run API (через `--aggregate-only`). |
| Q4 | **Status accuracy = primary metric** + confusion matrices | Status — головний verdict. Confusion показує що саме плутається (e.g., premature ↔ unresolved). |
| Q5 | **parser_reject_rate окремо, excluded з accuracy** | Reject = model violated V2 contract — окремий quality signal + blocker (>10% → filter). |
| Q6 | **Strength accuracy на 2-way (low/medium)** | Gold has 0 high — high prediction від моделі рахується wrong (OOD). |
| Q7 | **NO macro F1, NO composite score** | При n=32 + missing classes F1 noisy. Composite приховує що зламано. Decision framework з explicit steps — defensible. |
| Q8 | **NO LLM-as-judge** (direct enum compare) | Status/strength/value — discrete enums. Direct compare vinсе judge complexity. |
| Q9 | **Sequential per-model run** з throttle (Task 13 patterns) | No rate-limit risk, простіше. ~25-40 хв wall acceptable. |
| Q10 | **Cost = print estimate + user confirm**, no hard cap | Pet project, $1.70 total — trust. |

---

## Models (9, full sweep)

Перевикористовуємо `PROVIDER_API_KEY_ENV`, `CONCURRENCY_OVERRIDES`, `MIN_CALL_INTERVAL_SECONDS` з `scripts/evaluate_detection.py`. Додаємо entries для нових моделей (Gemini 2.5 Pro, GPT-5 full, Opus 4.6) якщо ще нема.

| Tier | Model | Чому |
|---|---|---|
| Cheap | `anthropic/claude-haiku-4-5` | Найдешевша Anthropic — кандидат на prod |
| Cheap | `openai/gpt-5-mini` | OpenAI reasoning-mini, strong structured output |
| Cheap | `gemini/gemini-3.1-flash-lite-preview` | Уже production extractor (Task 13.5), consistency |
| Cheap | `deepseek/deepseek-chat` | Найдешевший варіант |
| Cheap | `groq/llama-3.3-70b-versatile` | Open-weights baseline (free tier) |
| Mid | `gemini/gemini-2.5-pro` | Якісний Gemini, gradient |
| Expensive | `anthropic/claude-sonnet-4-6` | Anthropic quality baseline, вже у проекті |
| Expensive | `anthropic/claude-opus-4-6` | Anthropic ceiling — upper bound для F1 |
| Expensive | `openai/gpt-5` | OpenAI flagship, parity з Opus |

---

## Pipeline architecture

### Stage 1 — RUN (per-model)

```python
for model in selected_models:
    if skip_existing and per_model_file_exists(model):
        continue
    results = {}
    for gold_entry in gold_predictions:
        prompt = build_verification_prompt_v2(
            claim=gold_entry["claim_text"],
            prediction_date=gold_entry["prediction_date"],
            target_date=gold_entry["target_date"],
            today=gold_metadata["today"],          # "2026-05-23"
            situation=gold_entry["situation"],
        )
        system = get_verification_system_v2(today=gold_metadata["today"])
        start = monotonic()
        try:
            raw = await llm_client.complete(prompt, system=system)
            parsed = parse_verification_response_v2(raw)
            parse_error = None
        except ValueError as e:
            parsed = None
            parse_error = str(e)
        except Exception as e:
            parsed = None
            parse_error = f"infra: {type(e).__name__}: {e}"
        latency = monotonic() - start
        results[gold_entry["id"]] = {
            "raw_response": raw if 'raw' in locals() else None,
            "parsed": parsed,
            "parse_error": parse_error,
            "latency_seconds": latency,
            "cost_usd": estimate_cost(model, prompt, raw),
        }
        await throttle(model)
    save_per_model_file(model, results)
```

**Output:** `scripts/outputs/verification_eval/per_model/<provider>_<model>.json`

### Stage 2 — AGGREGATE

```python
files = glob("scripts/outputs/verification_eval/per_model/*.json")
per_model_metrics = {}
for file in files:
    data = load_json(file)
    metrics = compute_metrics_for_model(data["results"], gold_predictions)
    per_model_metrics[data["metadata"]["model"]] = metrics

decision = apply_decision_framework(per_model_metrics)
save_metrics_json(per_model_metrics, decision)
write_report_md(per_model_metrics, decision)
```

**Outputs:**
- `scripts/outputs/verification_eval/verification_eval_metrics.json`
- `scripts/outputs/verification_eval/verification_eval_report.md`

---

## Metrics

| Field | Metric | Notes |
|---|---|---|
| **status** | accuracy + **4×4 confusion** (gold-major) | Primary. Labels: confirmed/refuted/unresolved/premature |
| **prediction_strength** | accuracy + **2×2 confusion** | Тільки low/medium. Model "high" = wrong (OOD). |
| **prediction_value** | accuracy + **3×3 confusion** | low/medium/high — всі представлені в gold |
| **parser_reject_rate** | rejects / total_calls | Окрема метрика. Excluded з accuracy denominator. |
| **calibration** | `mean_conf_correct`, `mean_conf_wrong`, `gap` | Gap = signal для Task 20 route logic |
| **cost** | sum cost_usd | Production constraint |
| **latency** | mean of latency_seconds | Production constraint |

**Denominator для accuracy:** `n_predictions − n_parser_rejects` (тільки successfully parsed). Rejects окремо.

---

## Decision Framework (4-step)

```
Step 1: FILTER BLOCKERS
  Drop models if:
    - parser_reject_rate > 10%   (модель ненадійна)
    - status_accuracy < 0.5      (гірше монетки на 4 класах)

Step 2: QUALITY TIER
  max_acc = max(status_accuracy across survivors)
  tier = [m for m in survivors if m.status_accuracy >= max_acc − 0.1]

  Rationale: ±0.1 tolerance noise при n=32 (≈3 predictions)

Step 3: TIE-BREAK within tier
  Primary:   lowest cost_total_usd
  Secondary: lowest latency_mean
  Tertiary:  highest (strength_acc + value_acc)

Step 4: SANITY CHECK winner
  Inspect 5 disagreements (winner verdict ≠ gold):
    - Real model errors → accept (model has known weakness)
    - Gold borderline (we were unsure) → not real error
    - >2 disagreements show gold drift → re-label
```

---

## CLI

| Flag | Default | Effect |
|---|---|---|
| `--model M1,M2,...` | all configured (9) | comma-separated subset |
| `--skip-existing` | False | skip models що мають per-model output file (resume) |
| `--force` | False | overwrite existing per-model output (re-run model) |
| `--aggregate-only` | False | skip Stage 1, тільки Stage 2 |
| `--output-dir PATH` | `scripts/outputs/verification_eval/` | base dir |
| `--gold PATH` | `scripts/data/verification_gold_labels.json` | gold dataset |
| `--yes` | False | skip cost-confirm prompt |

**Default invocation:**

```bash
.venv/bin/python scripts/verification_eval.py
```

Cost estimate показується для моделей що **будуть** run (after skip-existing filter). Якщо user не передав `--yes`, prompt for `[y/N]` confirm.

---

## Per-model output schema

```json
{
  "metadata": {
    "model": "anthropic/claude-sonnet-4-6",
    "run_at": "2026-05-23T...",
    "gold_path": "scripts/data/verification_gold_labels.json",
    "today": "2026-05-23",
    "n_predictions": 32
  },
  "results": {
    "tg:O_Arestovich_official_1395:0": {
      "raw_response": "{...}",
      "parsed": {
        "status": "unresolved",
        "confidence": 0.6,
        "prediction_strength": "low",
        "prediction_value": "medium",
        "reasoning": "...",
        "evidence": null,
        "retry_after": null,
        "max_horizon": null
      } | null,
      "parse_error": "missing required field: prediction_value" | null,
      "latency_seconds": 2.34,
      "cost_usd": 0.0008
    },
    ...
  }
}
```

Filename: `<provider>_<model_with_slashes_to_underscores>.json`, e.g. `anthropic_claude-sonnet-4-6.json`.

---

## Aggregate metrics schema

```json
{
  "metadata": {"computed_at": "...", "n_gold": 32, "n_models_processed": 9},
  "per_model": {
    "anthropic/claude-sonnet-4-6": {
      "parsed_ok": 32,
      "parser_rejects": 0,
      "parser_reject_rate": 0.0,
      "status": {
        "accuracy": 0.81,
        "confusion": {
          "confirmed":  {"confirmed": 7, "refuted": 0, "unresolved": 1, "premature": 0},
          "refuted":    {"confirmed": 0, "refuted": 3, "unresolved": 1, "premature": 0},
          "unresolved": {"confirmed": 1, "refuted": 0, "unresolved": 7, "premature": 1},
          "premature":  {"confirmed": 0, "refuted": 0, "unresolved": 1, "premature": 10}
        }
      },
      "prediction_strength": {
        "accuracy": 0.74,
        "confusion": {
          "low":    {"low": 18, "medium": 4},
          "medium": {"low": 3,  "medium": 7}
        }
      },
      "prediction_value": {
        "accuracy": 0.66,
        "confusion": { ... 3×3 ... }
      },
      "calibration": {
        "mean_conf_correct": 0.78,
        "mean_conf_wrong":   0.61,
        "gap": 0.17
      },
      "cost_total_usd": 0.15,
      "latency_mean_seconds": 2.8
    },
    ...
  },
  "decision_framework": {
    "step1_filtered_out": [
      {"model": "deepseek/deepseek-chat", "reason": "reject_rate=14% > 10%"}
    ],
    "step2_max_status_acc": 0.84,
    "step2_quality_tier": ["claude-opus-4-6", "claude-sonnet-4-6", "openai/gpt-5"],
    "step3_winner": "anthropic/claude-sonnet-4-6",
    "step3_rationale": "Tier-1 з найнижчою cost ($0.15 vs Opus $0.50, GPT-5 $0.30)",
    "step4_disagreements_for_review": [
      {
        "id": "tg:O_Arestovich_official_4260:1",
        "gold_status": "unresolved", "model_status": "premature",
        "claim": "Успешность этой операции..."
      },
      ... 5 entries
    ]
  }
}
```

---

## Report (markdown) structure

```markdown
# Verification Model Evaluation Report

**Run:** 2026-05-23
**Gold:** 32 Arestovich predictions
**Models:** 9 (всі run)
**Total cost:** $1.83

## Decision: PRODUCTION VERIFIER = `anthropic/claude-sonnet-4-6`

Tier-1 (status_acc ≥ 0.74): Opus (0.84), Sonnet (0.81), GPT-5 (0.78).
Sonnet — найдешевша у tier ($0.15 vs Opus $0.50, GPT-5 $0.30).
parser_reject_rate = 0%.

## Ranking

| Rank | Model | Status acc | Strength acc | Value acc | Reject % | Cost | Latency | Verdict |
|---|---|---|---|---|---|---|---|---|

(rows sorted by status_accuracy desc, з verdict labels: WINNER / tier-1 / below tier / FILTERED)

## Per-model details

### `anthropic/claude-sonnet-4-6` — WINNER

**Status confusion (gold-major):** (4×4 table)
**Strength confusion:** (2×2 table)
**Value confusion:** (3×3 table)
**Calibration:** mean_conf_correct=X, wrong=Y, gap=+Z (well/mid/un-calibrated)

(... per-model sections for всіх моделей)

## Sanity check: 5 disagreements winner vs gold

(numbered list з claim + gold vs model verdict + inspection note)

## Common failure modes

(observations: e.g., unresolved↔premature confusion, OOD strength predictions, etc.)

## Recommendations

1. Production verifier = X
2. confidence route signal (якщо gap > 0.15)
3. V3 prompt improvements (якщо patterns у failure modes)
```

---

## Files

**Create:**
- `scripts/verification_eval.py` (~350-400 рядків)
- `tests/test_verification_eval.py` (~80 рядків, pure aggregation tests)

**Output (gitignored):**
- `scripts/outputs/verification_eval/per_model/*.json` (per-model)
- `scripts/outputs/verification_eval/verification_eval_metrics.json` (aggregated)
- `scripts/outputs/verification_eval/verification_eval_report.md` (markdown)

**Modify:**
- Можливо `scripts/evaluate_detection.py` — додати entries у CONCURRENCY_OVERRIDES, MIN_CALL_INTERVAL_SECONDS для нових моделей (Gemini 2.5 Pro, GPT-5 full, Opus 4.6) якщо ще нема. Reuse-only approach, не duplicate.

**No DB / domain / migration changes** — eval task, не торкається production data path.

---

## Tests (pure aggregation only)

| Test | Purpose |
|---|---|
| `test_compute_accuracy_from_pairs` | Pure function: list of (gold, pred) → accuracy float |
| `test_compute_confusion_matrix_4_classes` | status confusion gold-major dict |
| `test_compute_confusion_matrix_3_classes` | value confusion |
| `test_compute_confusion_matrix_2_classes` | strength low/medium |
| `test_calibration_gap_positive_signal` | mean_conf_correct > wrong → positive gap |
| `test_calibration_gap_uncalibrated` | similar means → gap ≈ 0 |
| `test_apply_decision_framework_filters_high_reject` | model з reject_rate > 0.1 виключається |
| `test_apply_decision_framework_filters_low_accuracy` | model з acc < 0.5 виключається |
| `test_apply_decision_framework_picks_winner_by_cost` | tier має 3 models → winner = cheapest |
| `test_apply_decision_framework_handles_all_filtered` | усі моделі fail → winner = None, reason captured |

**No pipeline integration tests** (Stage 1 робить API calls — ad-hoc smoke через `--limit` instead).

---

## Cost estimate (288 calls = 9 models × 32 predictions)

Approximate (prompt ~2k input + ~500 output tokens per call):

| Tier | Models | Per-model cost | Subtotal |
|---|---|---|---|
| Cheap (5) | Haiku, GPT-5-mini, Gemini Flash Lite, DeepSeek, Llama | ~$0.01-0.05 each | ~$0.10 |
| Mid (1) | Gemini 2.5 Pro | ~$0.10 | ~$0.10 |
| Expensive (3) | Sonnet 4.5, Opus 4.6, GPT-5 | ~$0.30-0.70 each | ~$1.50 |
| **Total** | | | **~$1.70** |

Wall time ~25-40 хв sequential з per-model throttle.

---

## Out of scope

- ❌ `retry_after` / `max_horizon` date proximity metric
- ❌ `confidence` MAE vs gold expected_confidence
- ❌ `evidence` / `reasoning` text comparison
- ❌ Macro F1 (noisy при n=32 + strength has 0 high)
- ❌ Composite single score
- ❌ LLM-as-judge для disagreements
- ❌ Pipeline integration tests
- ❌ Concurrent per-model runs
- ❌ Hard cost cap

---

## Cross-references

- **V2 verifier spec:** `../verifier-v2/2026-04-26-verification-trigger-policy-design.md`
- **Task 19.5 V2 foundations:** `../2026-05-07-task-19-5-schema-prompts-design.md`
- **Task 19.7a (gold v1):** `../2026-05-12-task-19-7a-gold-labeling-design.md`
- **Task 19.8d (situation):** `../19-8d-situation-field/design.md`
- **Pattern source (extraction quality eval):** `../../extraction-quality-eval/2026-04-21-extraction-quality-eval-design.md`
- **Detection eval pattern:** `scripts/evaluate_detection.py`
