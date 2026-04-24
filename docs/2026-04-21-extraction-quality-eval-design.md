# Extraction Quality Evaluation — Design (Task 13.5)

**Status:** Design approved, ready for implementation plan
**Date:** 2026-04-21
**Related:** Detection eval ([Task 13](2026-04-08-prophet-checker-plan.md)), annotation guidelines ([docs](annotation-guidelines.md))

## Context & Problem

**Task 13 (Detection Eval)** measured whether models correctly classify Arestovich posts as containing a prediction (binary YES/NO). Winner: Gemini 3.1 Flash Lite at F1=0.848.

But detection ≠ extraction quality. A model can correctly answer "yes, prediction present" while producing a poor `claim_text`:

- Hallucination: claim text isn't actually in the post
- Truncation: claim cut mid-sentence
- Not-a-prediction: extracted text is a slogan/announcement that doesn't satisfy our 3-criteria verifiability rule
- Metadata errors: wrong `prediction_date` / `target_date` / `topic`
- Paraphrase that loses meaning

The current `PredictionExtractor` ([src/prophet_checker/analysis/extractor.py](../src/prophet_checker/analysis/extractor.py)) has been invoked ~1000× during Task 13 but the extracted content was discarded. Extraction quality has never been verified.

**Goal:** Build an automated eval that measures extraction quality for 3 models using LLM-as-judge methodology. No manual annotation required.

## Non-Goals

- NOT measuring detection accuracy (covered by Task 13)
- NOT fine-tuning prompts or models (possible follow-up)
- NOT running on the full 5572-post dataset (Task 14 scope, deferred)
- NOT comparing all 5 Task 13 models — only 3 selected based on Task 13 results

## High-Level Architecture

Three decoupled stages, two intermediate persistent artifacts:

```
┌──────────────────────────────────────────────────────────────────┐
│  Stage 1: Extraction (3 models × 97 posts = 291 extractor calls) │
│                                                                  │
│    For each extractor in {gemini, deepseek, sonnet}:             │
│      For each of 97 gold-labeled Arestovich posts:               │
│        predictions = extractor.extract(post)  # DetectionLLM     │
│        save full predictions (not just bool)                     │
│                                                                  │
│    Artifact → scripts/extraction_outputs.json                    │
│                                                                  │
│  Stage 2: Judge (Opus 4.6, 291 judge calls)                      │
│                                                                  │
│    For each (extractor, post, extracted_claims):                 │
│      verdict_set = opus.judge(post_text, claims)                 │
│      save per_claim verdicts + missed_predictions list           │
│                                                                  │
│    Artifact → scripts/extraction_judgements.json                 │
│                                                                  │
│  Stage 3: Aggregate                                              │
│                                                                  │
│    Per extractor model compute:                                  │
│      - verdict distribution (categorical counts)                 │
│      - avg_quality_score (ordinal-mapped mean)                   │
│      - hallucination_rate                                        │
│      - missed_predictions_rate                                   │
│      - gold agreement/disagreement matrix                        │
│                                                                  │
│    Artifact → scripts/extraction_eval_report.json                │
│               + console comparison table                         │
└──────────────────────────────────────────────────────────────────┘
```

Stage separation enables:
- Re-running Stage 2 with different judge without re-extracting (reuse Stage 1 artifact)
- Re-running Stage 3 with different aggregations (reuse both earlier artifacts)
- Independent testing of each stage

## Scope

**Dataset:** 97 gold-labeled Arestovich posts from [scripts/gold_labels.json](../scripts/gold_labels.json) (15 YES / 82 NO).

**Extractor models (participants):**

| Model | Rationale |
|---|---|
| Gemini 3.1 Flash Lite | Task 13 detection winner (F1=0.848). Validates "good detection → good extraction?" |
| DeepSeek V3.1 | Task 13 runner-up (F1=0.743). Open-weight comparison. |
| Sonnet 4.6 | Not in Task 13. Premium-tier sanity check: does model size materially improve extraction? |

All extractors run the v2 `EXTRACTION_SYSTEM` prompt (current prod prompt in [prompts.py](../src/prophet_checker/llm/prompts.py)).

**Judge model:** Claude Opus 4.6 — gold-standard reliability, different from 2 of 3 participant families (bias-mitigated).

**Out of scope:** Haiku, GPT-5-mini, Llama. Their Task 13 results were poor (Llama over-refused at F1=0.125; Haiku at F1=0.348). Including them adds cost without insight.

## Budget

| Line item | Cost |
|---|---:|
| Extraction × 3 models (97 posts each) | $1.28 |
| Judge × 3 × 97 posts = 291 calls (Opus 4.6, ~1500 tok in / ~300 tok out + ~1000 tok guidelines) | $13.10 |
| Aggregation | $0.00 |
| **Total** | **~$14.38** |

Wall time estimate: ~2-3 hours (extraction with concurrency, judge sequential).

## Judge Prompt Design (Approved)

### What the judge sees

- **EN instructions** (standard best practice, Opus strongest on EN instructions)
- **UA/RU content** verbatim (post text + extracted claims)
- **Published date** of post (for date-sanity checks and historical context)
- **Annotation guidelines** embedded in system prompt: 3-criteria YES test + 6-category NO rubric (from [annotation-guidelines.md](annotation-guidelines.md))
- **Extracted claims** from ONE extractor at a time (per-post, blind extractor identity, one model per judge call)

### What the judge does NOT see

- Author name (risk: political bias contamination; no functional value)
- Gold label (risk: priming / self-fulfilling prophecy; destroys independent calibration signal)
- Other extractors' outputs (risk: comparative anchor bias; we want absolute scores)
- Extractor model identity (risk: brand loyalty bias)

### Judge task per call

For each extracted claim, return:
- `verdict` (categorical, 6 values — see below)
- `reasoning` (1-2 sentence justification)

Plus at the end:
- `missed_predictions` — array of text excerpts from post that ARE valid predictions but weren't extracted

## Scoring Scheme (Approved — Option A Categorical Verdict)

Each extracted claim receives one of six verdicts:

| Verdict | Ordinal | Definition | Actionable Interpretation |
|---|---:|---|---|
| `exact_match` | 3 | Verbatim or near-verbatim quote from post; all metadata correct | Extractor performed perfectly |
| `faithful_paraphrase` | 3 | Semantically correct rephrase; prediction captured; metadata correct | Acceptable production output |
| `valid_but_metadata_error` | 2 | Correct prediction identified, but wrong `prediction_date`/`target_date`/`topic` | Fix metadata extraction logic |
| `not_a_prediction` | 1 | Claim appears in post but fails 3-criteria YES rule (slogan / announcement / normative / vague) | Prompt needs tightening — extractor over-extracts |
| `truncated` | 1 | Cut mid-sentence; meaning lost or distorted | Model has output-token or chunking issue |
| `hallucination` | 0 | Claim text is not present in post and cannot be derived from it | Critical failure — model fabricates |

Ordinal mapping provides scalar `quality_score` for ranking; verdict distribution provides diagnostic breakdown.

## JSON Schemas

### Stage 1 Artifact — `extraction_outputs.json`

```json
{
  "metadata": {
    "timestamp": "2026-04-21T14:00:00Z",
    "dataset_path": "scripts/gold_labels.json",
    "dataset_size": 97,
    "extractors": ["gemini/gemini-3.1-flash-lite-preview", "deepseek/deepseek-chat", "anthropic/claude-sonnet-4-6"],
    "prompt_version": "v2"
  },
  "extractions": {
    "gemini/gemini-3.1-flash-lite-preview": {
      "O_Arestovich_official_6937": [
        {
          "claim_text": "Трамп припинить бойові дії в Україні до кінця квітня",
          "prediction_date": "2025-02-18",
          "target_date": "2025-04-30",
          "topic": "війна"
        }
      ]
    }
  }
}
```

### Stage 2 Artifact — `extraction_judgements.json`

```json
{
  "metadata": {
    "timestamp": "...",
    "judge": "anthropic/claude-opus-4-6",
    "source_extractions": "scripts/extraction_outputs.json"
  },
  "judgements": {
    "gemini/gemini-3.1-flash-lite-preview": {
      "O_Arestovich_official_6937": {
        "per_claim": [
          {
            "claim_text": "Трамп припинить бойові дії...",
            "verdict": "exact_match",
            "reasoning": "Verbatim quote from post paragraph 7. Metadata dates consistent."
          }
        ],
        "missed_predictions": [
          {
            "text_excerpt": "Путін і Трамп підпишуть угоду на особистій зустрічі",
            "why_valid": "Concrete prediction about specific event between named individuals"
          }
        ]
      }
    }
  }
}
```

### Stage 3 Artifact — `extraction_eval_report.json`

```json
{
  "per_model": {
    "gemini/gemini-3.1-flash-lite-preview": {
      "total_claims": 31,
      "verdict_distribution": {
        "exact_match": 5, "faithful_paraphrase": 12, "valid_but_metadata_error": 2,
        "not_a_prediction": 8, "truncated": 1, "hallucination": 3
      },
      "avg_quality_score": 2.1,
      "hallucination_rate": 0.097,
      "not_a_prediction_rate": 0.258,
      "missed_predictions_count": 4,
      "missed_rate": 0.27,
      "gold_agreement": {
        "gold_YES_with_valid_extraction": 11,
        "gold_YES_no_valid_extraction": 4,
        "gold_NO_with_extractions_labeled_valid": 2,
        "gold_NO_without_valid_extractions": 80
      }
    }
  }
}
```

## Component Breakdown

### New files

| File | Purpose |
|---|---|
| `scripts/extraction_quality_eval.py` | Orchestration — CLI, stage runners, factory imports from evaluate_detection.py |
| `scripts/extraction_judge_prompts.py` | Judge SYSTEM + USER prompt templates, parse helpers |
| `tests/test_extraction_quality_eval.py` | ~10 TDD tests covering stage separation |

### Reuse from existing

| Existing | Used for |
|---|---|
| `DetectionLLM` wrapper ([scripts/evaluate_detection.py](../scripts/evaluate_detection.py)) | Stage 1 extractors — skip embeddings (same infra reasons as Task 13) |
| `_default_extractor_factory` ([evaluate_detection.py](../scripts/evaluate_detection.py)) | Model instantiation |
| `CONCURRENCY_OVERRIDES`, `MIN_CALL_INTERVAL_SECONDS` ([evaluate_detection.py](../scripts/evaluate_detection.py)) | Rate-limit safe | 
| `EXTRACTION_SYSTEM`, `EXTRACTION_TEMPLATE` ([src/prophet_checker/llm/prompts.py](../src/prophet_checker/llm/prompts.py)) | v2 prompt that participants will use |
| Annotation guidelines ([docs/annotation-guidelines.md](annotation-guidelines.md)) | Source of 3-criteria YES + 6-category NO rules for judge prompt |

### No changes to existing production code

`PredictionExtractor`, `LLMClient`, `prompts.py` — unchanged. All new logic in `scripts/` and `tests/`.

## CLI

```bash
# Run full 3-stage pipeline with defaults
python scripts/extraction_quality_eval.py

# Run only Stage 1 (re-extraction, skip judge)
python scripts/extraction_quality_eval.py --stages 1

# Re-judge existing extractions (reuse Stage 1 artifact)
python scripts/extraction_quality_eval.py --stages 2,3

# Alternative judge (swap models)
python scripts/extraction_quality_eval.py --stages 2,3 \
    --judge anthropic/claude-sonnet-4-6

# Specific extractor subset
python scripts/extraction_quality_eval.py \
    --extractors gemini/gemini-3.1-flash-lite-preview,deepseek/deepseek-chat
```

## Test Strategy

TDD: tests written before implementation, all red initially.

### Group A: verdict parsing + aggregation (pure functions)
- `test_parse_judge_response_valid_json` — extracts per_claim + missed_predictions
- `test_parse_judge_response_invalid_verdict_falls_back` — unknown verdict → error, not crash
- `test_aggregate_metrics_empty_claims` — returns valid zero-filled report
- `test_aggregate_metrics_ordinal_mapping` — verifies ordinal → score conversion

### Group B: Stage orchestration (mocked LLMs)
- `test_stage1_runs_all_extractors_over_all_posts` — counts mock invocations
- `test_stage2_skips_posts_with_no_extractions` — judge not invoked when extractor returned []
- `test_stage3_handles_extractor_with_zero_valid_claims` — metrics computed correctly

### Group C: Integration (all stages with mocks)
- `test_full_pipeline_with_synthetic_data` — end-to-end with 3 synthetic posts
- `test_can_re_run_stage_2_only` — Stage 1 artifact reused, extractor not re-invoked
- `test_gold_agreement_matrix_computation` — YES/NO × valid/invalid-extraction counts

## Success Criteria

Design is considered successfully implemented when:

1. All tests pass (`pytest tests/test_extraction_quality_eval.py`)
2. Running pipeline produces all 3 artifact JSON files
3. Report shows `avg_quality_score` for each of 3 participant models
4. Report shows `hallucination_rate` distinguishable between models
5. Gold agreement matrix populated (agreement/disagreement counts non-trivial)
6. No regression in existing 63 tests

## Risk & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| Opus throttle at `num_retries=3` | Low | Falls back to sequential with `MIN_CALL_INTERVAL_SECONDS` pattern |
| Judge returns malformed JSON occasionally | Medium | `parse_judge_response` treats parse failures as errors, logged, claim skipped (tracked in errors bucket) |
| Sonnet 4.6 as extractor behaves very differently than in Task 13 (where untested) | Medium | Accept as exploratory data — that's the point of including Sonnet |
| Judge bias toward same-family extractor (Sonnet) | Medium | Document limitation; flag any Sonnet advantage for re-analysis with different judge |
| Cost overrun (>$20) | Low | $14.38 is conservative estimate; added ~$5 buffer in Opus guideline overhead |
| Gold labels contain errors revealed by judge disagreement | Medium/High | This is VALUABLE — gold_agreement matrix specifically captures these cases for review |

## Future Work (Explicit Non-Goals)

- **Iterate prompt** based on hallucination/error patterns — separate task after this eval
- **Add more models** — if results are ambiguous, consider adding GPT-5-mini and re-running
- **Scale to 5572 posts** — combined with Task 14 future smoke test
- **Fine-tune the extractor on failure cases** — requires more gold labels and annotation effort

## Open Questions Resolved During Brainstorm

| Q | Decision |
|---|---|
| Scale: binary vs 0-3 vs multi-axis? | Categorical 6-verdict (Option A) |
| Per-post or per-claim judge call? | Per-post (coverage measurement + efficiency) |
| Single extractor or multi-extractor per judge call? | Single (blind, independent ratings) |
| Include gold label? | No (avoid priming; preserve calibration signal) |
| Include annotation guidelines? | Yes (consistency with human standard) |
| Include author name? | No (bias risk; no functional value) |
| Labeled or blind extractor identity? | Blind (avoid brand bias) |
| Which extractors to evaluate? | Gemini 3.1 FL, DeepSeek V3.1, Sonnet 4.6 |
| Which judge? | Opus 4.6 |
| Judge prompt language? | EN instructions, UA/RU content |
