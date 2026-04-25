# Extraction Quality Evaluation Implementation Plan (Task 13.5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **MANDATORY GATE:** After completing each task, STOP and ask the user for explicit confirmation before proceeding to the next task. Show summary (files changed, tests passed, commit hash) and wait for "ok"/"go"/"next".

**Goal:** Build automated LLM-as-judge evaluation that measures the **quality of predictions extracted** by 3 LLM models (Gemini 3.1 Flash Lite, DeepSeek V3.1, Sonnet 4.6) on 97 gold-labeled Arestovich posts, using Opus 4.6 as judge.

**Architecture:** 3-stage pipeline with persistent JSON artifacts between stages. Stage 1 captures full extraction outputs from each model. Stage 2 invokes Opus judge to assign categorical verdicts (6 values) to each extracted claim. Stage 3 aggregates per-model metrics including hallucination rate, missed predictions, and gold-label agreement matrix. Each stage decoupled — re-running Stage 2 or 3 doesn't require re-running Stage 1.

**Tech Stack:** Python 3.11+, LiteLLM (multi-provider routing), pytest + pytest-asyncio, existing PredictionExtractor + DetectionLLM wrapper from Task 13.

**Spec:** [`prediction-tracker/docs/2026-04-21-extraction-quality-eval-design.md`](2026-04-21-extraction-quality-eval-design.md) (commit `403f2fb`)

---

## File Structure

| File | Status | Purpose |
|---|---|---|
| `scripts/extraction_judge_prompts.py` | NEW | Judge SYSTEM + USER templates, VERDICT enum + ordinal map, parse helpers |
| `scripts/extraction_quality_eval.py` | NEW | Stage runners (1/2/3), aggregate_metrics, CLI orchestration |
| `tests/test_extraction_quality_eval.py` | NEW | TDD tests across all 3 stages and pure functions |
| `scripts/extraction_outputs.json` | GENERATED | Stage 1 artifact — per-extractor extracted predictions per post |
| `scripts/extraction_judgements.json` | GENERATED | Stage 2 artifact — per-extractor judge verdicts per post |
| `scripts/extraction_eval_report.json` | GENERATED | Stage 3 artifact — final aggregated metrics |

**Reuse (no modification):**
- `DetectionLLM` wrapper (`scripts/evaluate_detection.py:181-197`) — skip embeddings
- `_default_extractor_factory` (`scripts/evaluate_detection.py:213-237`) — provider routing + API key wiring
- `CONCURRENCY_OVERRIDES`, `MIN_CALL_INTERVAL_SECONDS` (`scripts/evaluate_detection.py:62-78`) — rate-limit safety
- `EXTRACTION_SYSTEM` v2 (`src/prophet_checker/llm/prompts.py`) — production extraction prompt
- `LLMClient` (`src/prophet_checker/llm/client.py`) — LiteLLM-backed completion + embedding

**No production code changes.** All new logic in `scripts/` and `tests/`.

---

## Milestones

| Milestone | Tasks | Outcome |
|---|---|---|
| **M1: Pure functions** | 1-3 | Verdict enum, judge prompts, response parser, aggregate metrics — all unit-tested |
| **M2: Stage runners** | 4-6 | Stage 1 / Stage 2 / Stage 3 orchestration with mocked LLM tests |
| **M3: CLI + integration** | 7-8 | argparse main() + end-to-end mock-based integration test |
| **M4: Real run** | 9-10 | Dry run on 5 posts → full eval → report → docs sync |

Total tasks: **10**.

---

## Task 1: Judge prompt module — VERDICT enum + JUDGE_SYSTEM + JUDGE_TEMPLATE + build_judge_prompt

**Files:**
- Create: `prediction-tracker/scripts/extraction_judge_prompts.py`
- Test: `prediction-tracker/tests/test_extraction_quality_eval.py`

- [ ] **Step 1: Write the failing tests**

Create `prediction-tracker/tests/test_extraction_quality_eval.py`:

```python
"""TDD tests for Task 13.5 — Extraction Quality Evaluation pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from extraction_judge_prompts import (
    VERDICT_VALUES,
    VERDICT_ORDINAL,
    JUDGE_SYSTEM,
    build_judge_prompt,
)


# =============================================================================
# Group A1 — VERDICT enum + ordinal mapping
# =============================================================================


def test_verdict_values_are_six():
    """Six categorical verdicts per design spec."""
    assert set(VERDICT_VALUES) == {
        "exact_match",
        "faithful_paraphrase",
        "valid_but_metadata_error",
        "not_a_prediction",
        "truncated",
        "hallucination",
    }


def test_verdict_ordinal_mapping_matches_spec():
    """Ordinal scoring per design table — 0/1/2/3 per spec."""
    assert VERDICT_ORDINAL == {
        "exact_match": 3,
        "faithful_paraphrase": 3,
        "valid_but_metadata_error": 2,
        "not_a_prediction": 1,
        "truncated": 1,
        "hallucination": 0,
    }


def test_judge_system_contains_three_criteria_and_six_categories():
    """JUDGE_SYSTEM must reference 3-criteria YES and 6-category NO rubric."""
    assert "three criteria" in JUDGE_SYSTEM.lower()
    assert "future" in JUDGE_SYSTEM.lower()
    assert "verifiable" in JUDGE_SYSTEM.lower()
    # All 6 verdict labels mentioned in instructions
    for verdict in VERDICT_VALUES:
        assert verdict in JUDGE_SYSTEM


def test_build_judge_prompt_includes_post_text_and_claims():
    """build_judge_prompt formats post + claims into reviewer's user message."""
    post_text = "Контрнаступ почнеться влітку 2023."
    claims = [
        {
            "claim_text": "Контрнаступ почнеться влітку 2023",
            "prediction_date": "2023-01-15",
            "target_date": "2023-06-01",
            "topic": "війна",
        }
    ]
    prompt = build_judge_prompt(
        post_text=post_text, published_date="2023-01-15", extracted_claims=claims
    )
    assert post_text in prompt
    assert "Контрнаступ почнеться влітку 2023" in prompt
    assert "2023-01-15" in prompt  # published date
    assert "війна" in prompt


def test_build_judge_prompt_handles_empty_claims():
    """When extractor returned empty list, prompt must explicitly say so."""
    prompt = build_judge_prompt(
        post_text="some post", published_date="2024-01-01", extracted_claims=[]
    )
    assert "no claims" in prompt.lower() or "empty" in prompt.lower() or "0" in prompt
```

- [ ] **Step 2: Run tests — verify all fail**

```bash
cd prediction-tracker
.venv/bin/pytest tests/test_extraction_quality_eval.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'extraction_judge_prompts'`

- [ ] **Step 3: Implement `scripts/extraction_judge_prompts.py`**

Create the file:

```python
"""Judge prompt templates and verdict definitions for Task 13.5 extraction eval.

The judge (Opus 4.6) rates each extracted claim using a 6-value categorical
verdict. Ordinal mapping (0-3) provides a scalar `quality_score` for ranking.
"""
from __future__ import annotations

import json
import re

VERDICT_VALUES: tuple[str, ...] = (
    "exact_match",
    "faithful_paraphrase",
    "valid_but_metadata_error",
    "not_a_prediction",
    "truncated",
    "hallucination",
)

VERDICT_ORDINAL: dict[str, int] = {
    "exact_match": 3,
    "faithful_paraphrase": 3,
    "valid_but_metadata_error": 2,
    "not_a_prediction": 1,
    "truncated": 1,
    "hallucination": 0,
}


JUDGE_SYSTEM = """You are evaluating the quality of prediction extraction from Ukrainian/Russian political commentary posts.

A valid prediction must satisfy ALL three criteria:
1. Refers to a FUTURE event or state (not present assessment, not past event)
2. Has a VERIFIABLE OUTCOME — a concrete condition that can be objectively checked as true or false later
3. Concerns EXTERNAL events (politics, war, economy, people, institutions) — NOT the author's own scheduled activities

Do NOT accept these as predictions (they superficially look like predictions but fail criteria above):

A. Slogans / rhetorical declarations without measurable outcomes (e.g. "Перемога буде за нами", "Військові злочинці понесуть відповідальність").
B. Author's own event announcements about broadcasts, courses, books, trips (e.g. "Завтра о 22:00 проведемо ефір").
C. Normative statements describing what SHOULD happen (e.g. "Потрібно посилити санкції", "Україна має змінити стратегію").
D. Vague forward statements without concrete criteria (e.g. "Найближчі тижні будуть переломними", "Ситуація скоро зміниться").
E. Analysis of present state or past events phrased with future-tense verbs for rhetorical effect (e.g. "Ця війна вже змінила світ").
F. Questions, calls to action, metaphors, sarcasm — these are not claims.

Verification test: ask "Could an impartial fact-checker in 1 year objectively confirm or refute this specific statement?" If the answer requires interpretation of vague terms — it's NOT a prediction.

For each extracted claim, assign exactly ONE of these six verdicts:

- exact_match: The claim is a verbatim or near-verbatim quote from the post AND is itself a valid prediction (passes all three criteria above) AND its prediction_date / target_date / topic metadata is correct.
- faithful_paraphrase: The claim is a semantically faithful rephrase of a valid prediction in the post AND metadata is correct. Minor rewording allowed.
- valid_but_metadata_error: The claim correctly identifies a valid prediction in the post, but the prediction_date, target_date, or topic metadata is wrong or inconsistent with the text.
- not_a_prediction: The claim text appears in the post but does NOT pass the three-criteria test (it's a slogan, announcement, normative, vague, present-tense rhetoric, etc. — categories A-F above).
- truncated: The claim is cut mid-sentence; the meaning is incomplete or distorted.
- hallucination: The claim text is NOT present in the post and cannot be reasonably derived from it. The extractor fabricated content.

Additionally, identify any predictions that ARE present in the post text but were NOT included in the extracted claims list. Report these as `missed_predictions`.

Respond ONLY with raw JSON in this exact shape — do NOT wrap in markdown code fences:

{
  "per_claim": [
    {
      "claim_text": "<verbatim claim from input>",
      "verdict": "<one of the six verdict values>",
      "reasoning": "<one or two sentences explaining the verdict>"
    }
  ],
  "missed_predictions": [
    {
      "text_excerpt": "<short quote from the post that was missed>",
      "why_valid": "<one sentence explaining why this is a valid prediction>"
    }
  ]
}

If the extracted claims list is empty, return per_claim as an empty list and only populate missed_predictions if applicable.
"""


JUDGE_TEMPLATE = """Post published on {published_date}:
---
{post_text}
---

The following claims were extracted by an LLM from the post:

{claims_block}

For each claim above, output a verdict per the rubric. Also identify any predictions in the post that the extractor missed.
"""


def build_judge_prompt(
    post_text: str, published_date: str, extracted_claims: list[dict]
) -> str:
    """Render the user-message judge prompt for a given post + claims."""
    if not extracted_claims:
        claims_block = "(no claims extracted — list is empty)"
    else:
        lines = []
        for idx, claim in enumerate(extracted_claims, start=1):
            lines.append(
                f"{idx}. \"{claim.get('claim_text', '')}\" "
                f"(prediction_date: {claim.get('prediction_date')}, "
                f"target_date: {claim.get('target_date')}, "
                f"topic: {claim.get('topic')})"
            )
        claims_block = "\n".join(lines)

    return JUDGE_TEMPLATE.format(
        post_text=post_text,
        published_date=published_date,
        claims_block=claims_block,
    )
```

- [ ] **Step 4: Update pytest pythonpath if needed**

`pyproject.toml` already has `pythonpath = ["src", "scripts"]` from Task 13. No change needed.

- [ ] **Step 5: Run tests — verify all pass**

```bash
.venv/bin/pytest tests/test_extraction_quality_eval.py -v
```

Expected: PASS — all 5 tests green.

- [ ] **Step 6: Commit**

```bash
git add scripts/extraction_judge_prompts.py tests/test_extraction_quality_eval.py
git commit -m "feat: judge prompts module with 6-verdict enum (Task 13.5 step 1)"
```

**🏁 End of Task 1.** STOP. Report: created scripts/extraction_judge_prompts.py + 5 passing tests, commit hash. Wait for "ok"/"next".

---

## Task 2: parse_judge_response — extract per_claim + missed_predictions from raw judge output

**Files:**
- Modify: `prediction-tracker/scripts/extraction_judge_prompts.py` (add parse_judge_response)
- Test: `prediction-tracker/tests/test_extraction_quality_eval.py` (add Group A2)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_extraction_quality_eval.py`:

```python
from extraction_judge_prompts import parse_judge_response


# =============================================================================
# Group A2 — parse_judge_response
# =============================================================================


def test_parse_judge_response_valid_json():
    """Standard well-formed JSON response is parsed into structured dict."""
    response = json.dumps(
        {
            "per_claim": [
                {
                    "claim_text": "X buy Y",
                    "verdict": "faithful_paraphrase",
                    "reasoning": "Captures the prediction",
                }
            ],
            "missed_predictions": [
                {"text_excerpt": "Z will fall", "why_valid": "Concrete event"}
            ],
        }
    )
    parsed = parse_judge_response(response)
    assert len(parsed["per_claim"]) == 1
    assert parsed["per_claim"][0]["verdict"] == "faithful_paraphrase"
    assert len(parsed["missed_predictions"]) == 1


def test_parse_judge_response_strips_markdown_fence():
    """Like extractor parser, must tolerate ```json...``` wrappers."""
    response = (
        "```json\n"
        + json.dumps({"per_claim": [], "missed_predictions": []})
        + "\n```"
    )
    parsed = parse_judge_response(response)
    assert parsed == {"per_claim": [], "missed_predictions": []}


def test_parse_judge_response_invalid_json_returns_error_marker():
    """Malformed JSON is reported as parse error, not raised."""
    parsed = parse_judge_response("not json at all")
    assert parsed["per_claim"] == []
    assert parsed["missed_predictions"] == []
    assert parsed.get("parse_error") is not None


def test_parse_judge_response_unknown_verdict_falls_back_to_marker():
    """Verdict outside the 6 allowed values is preserved but flagged."""
    response = json.dumps(
        {
            "per_claim": [
                {
                    "claim_text": "X",
                    "verdict": "totally_made_up",
                    "reasoning": "...",
                }
            ],
            "missed_predictions": [],
        }
    )
    parsed = parse_judge_response(response)
    assert parsed["per_claim"][0]["verdict"] == "totally_made_up"
    assert parsed["per_claim"][0].get("verdict_invalid") is True


def test_parse_judge_response_missing_top_level_keys_defaults_empty():
    """If response only has per_claim, missed_predictions defaults to []."""
    response = json.dumps(
        {
            "per_claim": [
                {"claim_text": "X", "verdict": "exact_match", "reasoning": "..."}
            ]
        }
    )
    parsed = parse_judge_response(response)
    assert parsed["missed_predictions"] == []
    assert len(parsed["per_claim"]) == 1
```

- [ ] **Step 2: Run new tests — verify they fail**

```bash
.venv/bin/pytest tests/test_extraction_quality_eval.py -v
```

Expected: 5 new tests FAIL with `ImportError: cannot import name 'parse_judge_response'`

- [ ] **Step 3: Implement parse_judge_response**

Append to `scripts/extraction_judge_prompts.py`:

```python
_CODE_FENCE_RE = re.compile(
    r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL,
)


def _strip_code_fence(text: str) -> str:
    match = _CODE_FENCE_RE.match(text.strip())
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_judge_response(response: str) -> dict:
    """Parse Opus judge output into normalized dict.

    Returns dict with keys:
        per_claim: list of {claim_text, verdict, reasoning, [verdict_invalid]}
        missed_predictions: list of {text_excerpt, why_valid}
        parse_error: str or None — populated when JSON is malformed

    Unknown verdict values are preserved with `verdict_invalid: True` flag,
    so the aggregator can count them separately. Malformed JSON returns
    empty lists with parse_error populated.
    """
    try:
        data = json.loads(_strip_code_fence(response))
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        return {
            "per_claim": [],
            "missed_predictions": [],
            "parse_error": f"{type(e).__name__}: {e}",
        }

    per_claim = data.get("per_claim", []) or []
    missed = data.get("missed_predictions", []) or []

    # Flag unknown verdicts but preserve them for diagnosis
    for item in per_claim:
        if item.get("verdict") not in VERDICT_VALUES:
            item["verdict_invalid"] = True

    return {
        "per_claim": per_claim,
        "missed_predictions": missed,
        "parse_error": None,
    }
```

- [ ] **Step 4: Run tests — verify all pass**

```bash
.venv/bin/pytest tests/test_extraction_quality_eval.py -v
```

Expected: 10 tests PASS (5 from Task 1 + 5 from Task 2).

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction_judge_prompts.py tests/test_extraction_quality_eval.py
git commit -m "feat: parse_judge_response with fence-strip + unknown-verdict flagging (Task 13.5 step 2)"
```

**🏁 End of Task 2.** STOP. Report status. Wait for "ok"/"next".

---

## Task 3: aggregate_metrics — compute per-model report from judgements + gold

**Files:**
- Create: `prediction-tracker/scripts/extraction_quality_eval.py` (with aggregate_metrics)
- Test: `prediction-tracker/tests/test_extraction_quality_eval.py` (add Group A3)

> **Plan revision (2026-04-21):** original plan did not handle `parse_error` from `parse_judge_response` — would have silently treated judge parse-failures as "model produced no valid extractions", contaminating `gold_agreement` matrix. Added: (1) `parse_error_count` tracking field, (2) **exclude** parse-error posts from `gold_agreement` (treat as missing data), (3) one new test asserting both behaviors.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_extraction_quality_eval.py`:

```python
from extraction_quality_eval import aggregate_metrics


# =============================================================================
# Group A3 — aggregate_metrics
# =============================================================================


def _gold(yes_ids, no_ids):
    """Helper to build gold-label list."""
    return [{"id": i, "has_prediction": True} for i in yes_ids] + [
        {"id": i, "has_prediction": False} for i in no_ids
    ]


def test_aggregate_metrics_empty_judgements():
    """No judgements → empty per_model section, no errors."""
    report = aggregate_metrics(judgements={}, gold_labels=_gold(["a"], ["b"]))
    assert report["per_model"] == {}


def test_aggregate_metrics_verdict_distribution_and_avg_score():
    """Single model with known verdict mix produces correct distribution + avg ordinal."""
    judgements = {
        "model_x": {
            "post_1": {
                "per_claim": [
                    {"verdict": "exact_match"},
                    {"verdict": "hallucination"},
                ],
                "missed_predictions": [],
            },
            "post_2": {
                "per_claim": [{"verdict": "faithful_paraphrase"}],
                "missed_predictions": [],
            },
        }
    }
    report = aggregate_metrics(
        judgements=judgements,
        gold_labels=_gold(["post_1", "post_2"], []),
    )
    m = report["per_model"]["model_x"]
    assert m["total_claims"] == 3
    assert m["verdict_distribution"]["exact_match"] == 1
    assert m["verdict_distribution"]["faithful_paraphrase"] == 1
    assert m["verdict_distribution"]["hallucination"] == 1
    # Ordinal sum: 3 + 0 + 3 = 6 over 3 claims = 2.0
    assert m["avg_quality_score"] == pytest.approx(2.0, abs=1e-6)
    assert m["hallucination_rate"] == pytest.approx(1 / 3, abs=1e-6)


def test_aggregate_metrics_missed_predictions_counted():
    """missed_predictions across posts contribute to missed_rate vs gold_YES count."""
    judgements = {
        "model_x": {
            "post_1": {
                "per_claim": [{"verdict": "exact_match"}],
                "missed_predictions": [{"text_excerpt": "X", "why_valid": "..."}],
            },
            "post_2": {
                "per_claim": [],
                "missed_predictions": [
                    {"text_excerpt": "Y", "why_valid": "..."},
                    {"text_excerpt": "Z", "why_valid": "..."},
                ],
            },
        }
    }
    report = aggregate_metrics(
        judgements=judgements, gold_labels=_gold(["post_1", "post_2"], [])
    )
    m = report["per_model"]["model_x"]
    assert m["missed_predictions_count"] == 3


def test_aggregate_metrics_gold_agreement_matrix():
    """Cross-tab judge verdicts vs gold labels."""
    judgements = {
        "model_x": {
            # Gold YES + has valid extraction → agreement
            "yes_with_valid": {
                "per_claim": [{"verdict": "faithful_paraphrase"}],
                "missed_predictions": [],
            },
            # Gold YES but no valid extraction → disagreement
            "yes_no_valid": {
                "per_claim": [{"verdict": "hallucination"}],
                "missed_predictions": [],
            },
            # Gold NO but has extraction labeled valid → disagreement (FP)
            "no_with_valid": {
                "per_claim": [{"verdict": "exact_match"}],
                "missed_predictions": [],
            },
            # Gold NO + no valid extractions → agreement
            "no_no_valid": {
                "per_claim": [{"verdict": "not_a_prediction"}],
                "missed_predictions": [],
            },
        }
    }
    report = aggregate_metrics(
        judgements=judgements,
        gold_labels=_gold(
            ["yes_with_valid", "yes_no_valid"],
            ["no_with_valid", "no_no_valid"],
        ),
    )
    matrix = report["per_model"]["model_x"]["gold_agreement"]
    assert matrix["gold_YES_with_valid_extraction"] == 1
    assert matrix["gold_YES_no_valid_extraction"] == 1
    assert matrix["gold_NO_with_extractions_labeled_valid"] == 1
    assert matrix["gold_NO_without_valid_extractions"] == 1


def test_aggregate_metrics_handles_invalid_verdict():
    """Verdict marked verdict_invalid is counted but excluded from ordinal mean."""
    judgements = {
        "model_x": {
            "post_1": {
                "per_claim": [
                    {"verdict": "exact_match"},
                    {"verdict": "totally_made_up", "verdict_invalid": True},
                ],
                "missed_predictions": [],
            }
        }
    }
    report = aggregate_metrics(
        judgements=judgements, gold_labels=_gold(["post_1"], [])
    )
    m = report["per_model"]["model_x"]
    assert m["total_claims"] == 2
    assert m["invalid_verdict_count"] == 1
    # avg only over valid verdicts: 3.0 / 1 = 3.0
    assert m["avg_quality_score"] == pytest.approx(3.0, abs=1e-6)


def test_aggregate_metrics_handles_parse_error():
    """Posts with parse_error must be counted but excluded from gold_agreement.

    A judge parse-failure is an INFRA issue, not a model failure. We should
    track count for visibility but NOT penalize the model in gold_agreement
    matrix (treat as missing data).
    """
    judgements = {
        "model_x": {
            # Successful judgement — gold_YES, valid extraction → counted
            "yes_ok": {
                "per_claim": [{"verdict": "exact_match"}],
                "missed_predictions": [],
                "parse_error": None,
            },
            # Judge parse failed on gold_YES post — should NOT be counted
            # as gold_YES_no_valid_extraction (since we don't actually know).
            "yes_parse_failed": {
                "per_claim": [],
                "missed_predictions": [],
                "parse_error": "JSONDecodeError: line 1 column 5",
            },
            # Judge parse failed on gold_NO post — also excluded.
            "no_parse_failed": {
                "per_claim": [],
                "missed_predictions": [],
                "parse_error": "TypeError: unexpected token",
            },
        }
    }
    report = aggregate_metrics(
        judgements=judgements,
        gold_labels=_gold(["yes_ok", "yes_parse_failed"], ["no_parse_failed"]),
    )
    m = report["per_model"]["model_x"]
    assert m["parse_error_count"] == 2
    matrix = m["gold_agreement"]
    # Only "yes_ok" contributes — parse-error posts excluded
    assert matrix["gold_YES_with_valid_extraction"] == 1
    assert matrix["gold_YES_no_valid_extraction"] == 0
    assert matrix["gold_NO_with_extractions_labeled_valid"] == 0
    assert matrix["gold_NO_without_valid_extractions"] == 0
```

- [ ] **Step 2: Run new tests — verify they fail**

```bash
.venv/bin/pytest tests/test_extraction_quality_eval.py::test_aggregate_metrics_empty_judgements -v
```

Expected: FAIL — `ImportError: cannot import name 'aggregate_metrics' from 'extraction_quality_eval'`

- [ ] **Step 3: Create extraction_quality_eval.py with aggregate_metrics**

Create `scripts/extraction_quality_eval.py`:

```python
#!/usr/bin/env python3
"""Extraction Quality Evaluation — Task 13.5.

LLM-as-judge eval for prediction extraction quality across 3 models.
See spec: docs/2026-04-21-extraction-quality-eval-design.md
"""
from __future__ import annotations

from collections import Counter

from extraction_judge_prompts import VERDICT_ORDINAL, VERDICT_VALUES


# =============================================================================
# Aggregation (pure)
# =============================================================================


def _empty_distribution() -> dict[str, int]:
    return {v: 0 for v in VERDICT_VALUES}


def aggregate_metrics(
    judgements: dict, gold_labels: list[dict]
) -> dict:
    """Compute per-model summary report from judgements + gold labels.

    Args:
        judgements: {extractor_id: {post_id: {per_claim: [...], missed_predictions: [...]}}}
        gold_labels: list of {"id": str, "has_prediction": bool}

    Returns:
        {"per_model": {extractor_id: {...metrics...}}}
    """
    gold_index = {g["id"]: g["has_prediction"] for g in gold_labels}
    per_model: dict[str, dict] = {}

    for extractor_id, posts in judgements.items():
        verdict_counts = _empty_distribution()
        invalid_count = 0
        parse_error_count = 0
        ordinal_sum = 0
        ordinal_n = 0
        missed_total = 0
        gold_yes_with_valid = 0
        gold_yes_no_valid = 0
        gold_no_with_valid = 0
        gold_no_no_valid = 0

        for post_id, j in posts.items():
            # Skip parse-error posts entirely (infra failure, not model failure).
            # Counted for visibility but excluded from gold_agreement matrix.
            if j.get("parse_error") is not None:
                parse_error_count += 1
                continue

            claims = j.get("per_claim", [])
            missed = j.get("missed_predictions", [])
            missed_total += len(missed)

            has_valid_extraction = False
            for c in claims:
                v = c.get("verdict")
                if c.get("verdict_invalid") or v not in VERDICT_VALUES:
                    invalid_count += 1
                    continue
                verdict_counts[v] += 1
                ordinal_sum += VERDICT_ORDINAL[v]
                ordinal_n += 1
                if VERDICT_ORDINAL[v] >= 2:  # exact_match, faithful_paraphrase, valid_but_metadata_error
                    has_valid_extraction = True

            gold_yes = gold_index.get(post_id)
            if gold_yes is True:
                if has_valid_extraction:
                    gold_yes_with_valid += 1
                else:
                    gold_yes_no_valid += 1
            elif gold_yes is False:
                if has_valid_extraction:
                    gold_no_with_valid += 1
                else:
                    gold_no_no_valid += 1

        total_claims = sum(verdict_counts.values()) + invalid_count
        avg_score = (ordinal_sum / ordinal_n) if ordinal_n > 0 else 0.0
        hallucination_rate = (
            verdict_counts["hallucination"] / total_claims
            if total_claims > 0
            else 0.0
        )
        gold_yes_total = gold_yes_with_valid + gold_yes_no_valid
        missed_rate = (missed_total / gold_yes_total) if gold_yes_total > 0 else 0.0

        per_model[extractor_id] = {
            "total_claims": total_claims,
            "invalid_verdict_count": invalid_count,
            "parse_error_count": parse_error_count,
            "verdict_distribution": verdict_counts,
            "avg_quality_score": round(avg_score, 3),
            "hallucination_rate": round(hallucination_rate, 3),
            "missed_predictions_count": missed_total,
            "missed_rate": round(missed_rate, 3),
            "gold_agreement": {
                "gold_YES_with_valid_extraction": gold_yes_with_valid,
                "gold_YES_no_valid_extraction": gold_yes_no_valid,
                "gold_NO_with_extractions_labeled_valid": gold_no_with_valid,
                "gold_NO_without_valid_extractions": gold_no_no_valid,
            },
        }

    return {"per_model": per_model}
```

- [ ] **Step 4: Run tests — verify all pass**

```bash
.venv/bin/pytest tests/test_extraction_quality_eval.py -v
```

Expected: 16 tests PASS (10 from Tasks 1-2 + 6 new aggregate tests including parse_error handling).

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction_quality_eval.py tests/test_extraction_quality_eval.py
git commit -m "feat: aggregate_metrics with verdict distribution + gold agreement matrix + parse_error handling (Task 13.5 step 3)"
```

**🏁 End of Task 3.** STOP. Report. Wait for "ok"/"next".

---

## Task 4: Stage 1 — run_stage1_extraction (orchestrate extractor calls + save artifact)

**Files:**
- Modify: `prediction-tracker/scripts/extraction_quality_eval.py` (add Stage 1)
- Test: `prediction-tracker/tests/test_extraction_quality_eval.py` (add Group B1)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_extraction_quality_eval.py`:

```python
import asyncio
from datetime import date
from uuid import uuid4

from extraction_quality_eval import run_stage1_extraction


# =============================================================================
# Group B1 — Stage 1 orchestration (mocked extractor)
# =============================================================================


def _fake_pred(claim: str, topic: str = "війна") -> MagicMock:
    """Create a Prediction-like object with the fields Stage 1 reads."""
    p = MagicMock()
    p.claim_text = claim
    p.prediction_date = date(2024, 1, 15)
    p.target_date = date(2024, 6, 1)
    p.topic = topic
    return p


def _make_factory(claim_map: dict[str, list[str]]):
    """Build extractor_factory that returns mock extractors emitting fixed claims per post.

    claim_map: {extractor_id: {post_id: [claim_text, ...]}}
    """
    def factory(model_id: str):
        extractor = MagicMock()

        async def fake_extract(*, document_id, **kwargs):
            claims = claim_map.get(model_id, {}).get(document_id, [])
            return [_fake_pred(c) for c in claims]

        extractor.extract = AsyncMock(side_effect=fake_extract)
        return extractor

    return factory


async def test_stage1_invokes_each_extractor_per_post(tmp_path):
    posts = [
        {"id": "p1", "person_name": "Арестович", "published_at": "2024-01-01", "text": "T1"},
        {"id": "p2", "person_name": "Арестович", "published_at": "2024-01-02", "text": "T2"},
    ]
    claim_map = {
        "model_a": {"p1": ["claim_a1"], "p2": ["claim_a2_1", "claim_a2_2"]},
        "model_b": {"p1": ["claim_b1"], "p2": []},
    }
    out_path = tmp_path / "extractions.json"

    await run_stage1_extraction(
        extractors=["model_a", "model_b"],
        posts=posts,
        author_filter="Арестович",
        output_path=out_path,
        extractor_factory=_make_factory(claim_map),
    )

    saved = json.loads(out_path.read_text())
    assert "extractions" in saved
    assert set(saved["extractions"].keys()) == {"model_a", "model_b"}
    assert len(saved["extractions"]["model_a"]["p1"]) == 1
    assert saved["extractions"]["model_a"]["p1"][0]["claim_text"] == "claim_a1"
    assert len(saved["extractions"]["model_a"]["p2"]) == 2
    assert saved["extractions"]["model_b"]["p2"] == []


async def test_stage1_filters_posts_by_author(tmp_path):
    posts = [
        {"id": "p1", "person_name": "Арестович", "published_at": "2024-01-01", "text": "T1"},
        {"id": "p2", "person_name": "Гордон", "published_at": "2024-01-02", "text": "T2"},
    ]
    claim_map = {"model_a": {"p1": ["c1"], "p2": ["c2"]}}
    out_path = tmp_path / "extractions.json"

    await run_stage1_extraction(
        extractors=["model_a"],
        posts=posts,
        author_filter="Арестович",
        output_path=out_path,
        extractor_factory=_make_factory(claim_map),
    )

    saved = json.loads(out_path.read_text())
    # p2 (Гордон) excluded
    assert set(saved["extractions"]["model_a"].keys()) == {"p1"}


async def test_stage1_handles_extractor_exception_as_empty_list(tmp_path):
    posts = [{"id": "p1", "person_name": "Арестович", "published_at": "2024-01-01", "text": "T"}]
    out_path = tmp_path / "extractions.json"

    def factory(model_id):
        m = MagicMock()
        m.extract = AsyncMock(side_effect=RuntimeError("API down"))
        return m

    await run_stage1_extraction(
        extractors=["model_a"],
        posts=posts,
        author_filter="Арестович",
        output_path=out_path,
        extractor_factory=factory,
    )

    saved = json.loads(out_path.read_text())
    # Errors logged separately, post key still present with empty claims
    assert saved["extractions"]["model_a"]["p1"] == []
    assert "p1" in saved["errors"]["model_a"]
```

- [ ] **Step 2: Run new tests — verify they fail**

Expected: 3 new tests FAIL — `cannot import name 'run_stage1_extraction'`

- [ ] **Step 3: Implement run_stage1_extraction**

Append to `scripts/extraction_quality_eval.py`:

```python
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


def _serialize_prediction(p) -> dict:
    """Convert a Prediction domain object to JSON-friendly dict."""
    return {
        "claim_text": p.claim_text,
        "prediction_date": p.prediction_date.isoformat() if p.prediction_date else None,
        "target_date": p.target_date.isoformat() if p.target_date else None,
        "topic": p.topic,
    }


async def run_stage1_extraction(
    extractors: list[str],
    posts: list[dict],
    author_filter: str,
    output_path: Path,
    extractor_factory: Callable,
    concurrency: int = 5,
) -> None:
    """Run each extractor over filtered posts, save full extractions to disk.

    Errors during extraction are logged into a separate `errors` map per model;
    the post still appears in `extractions` with an empty claims list.
    """
    filtered_posts = [p for p in posts if p["person_name"] == author_filter]
    extractions: dict[str, dict[str, list[dict]]] = {m: {} for m in extractors}
    errors: dict[str, dict[str, str]] = {m: {} for m in extractors}

    for model_id in extractors:
        extractor = extractor_factory(model_id)
        sem = asyncio.Semaphore(concurrency)

        async def process(post: dict) -> tuple[str, list[dict] | None, str | None]:
            async with sem:
                try:
                    preds = await extractor.extract(
                        text=post["text"],
                        person_id=post["person_name"],
                        document_id=post["id"],
                        person_name=post["person_name"],
                        published_date=post["published_at"],
                    )
                    return post["id"], [_serialize_prediction(p) for p in preds], None
                except Exception as e:
                    logger.exception("Extraction failed for %s on %s", model_id, post["id"])
                    return post["id"], [], f"{type(e).__name__}: {e}"

        results = await asyncio.gather(*(process(p) for p in filtered_posts))
        for post_id, claims, err in results:
            extractions[model_id][post_id] = claims if claims is not None else []
            if err:
                errors[model_id][post_id] = err

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "dataset_size": len(filtered_posts),
                    "extractors": list(extractors),
                    "author_filter": author_filter,
                },
                "extractions": extractions,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run tests — verify all pass**

```bash
.venv/bin/pytest tests/test_extraction_quality_eval.py -v
```

Expected: 18 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction_quality_eval.py tests/test_extraction_quality_eval.py
git commit -m "feat: run_stage1_extraction — concurrent extractor orchestration with error capture (Task 13.5 step 4)"
```

**🏁 End of Task 4.** STOP. Report. Wait for "ok"/"next".

---

## Task 5: Stage 2 — run_stage2_judge (call Opus per (extractor, post), save verdicts)

**Files:**
- Modify: `prediction-tracker/scripts/extraction_quality_eval.py` (add Stage 2)
- Test: `prediction-tracker/tests/test_extraction_quality_eval.py` (add Group B2)

> **Plan revision (2026-04-21):** added CLI logging for parse_error count after Stage 2 completes (visibility into infra issues during eval). The artifact already preserves `parse_error` field per Task 2 design — this revision just surfaces the count.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_extraction_quality_eval.py`:

```python
from extraction_quality_eval import run_stage2_judge


# =============================================================================
# Group B2 — Stage 2 orchestration (mocked judge LLM)
# =============================================================================


def _make_judge_factory(response_map: dict[str, str]):
    """Factory that returns judge LLM whose .complete() returns canned response.

    response_map: {post_id_or_keyword: judge_response_text}
    """
    def factory(judge_id: str):
        client = MagicMock()

        async def fake_complete(prompt: str, system: str | None = None):
            # naive lookup: find first response_map key present in prompt
            for key, resp in response_map.items():
                if key in prompt:
                    return resp
            return json.dumps({"per_claim": [], "missed_predictions": []})

        client.complete = AsyncMock(side_effect=fake_complete)
        return client

    return factory


async def test_stage2_invokes_judge_per_extractor_post(tmp_path):
    extractions_artifact = {
        "metadata": {"extractors": ["model_a", "model_b"]},
        "extractions": {
            "model_a": {
                "p1": [{"claim_text": "claim_a1", "prediction_date": "2024-01-01",
                        "target_date": None, "topic": "війна"}],
            },
            "model_b": {
                "p1": [],
            },
        },
        "errors": {"model_a": {}, "model_b": {}},
    }
    extractions_path = tmp_path / "extractions.json"
    extractions_path.write_text(json.dumps(extractions_artifact, ensure_ascii=False))
    posts = [{"id": "p1", "person_name": "Арестович", "published_at": "2024-01-01",
              "text": "Some Ukrainian post text"}]
    out_path = tmp_path / "judgements.json"

    response_map = {
        "claim_a1": json.dumps({
            "per_claim": [
                {"claim_text": "claim_a1", "verdict": "exact_match", "reasoning": "ok"}
            ],
            "missed_predictions": [],
        }),
    }

    await run_stage2_judge(
        judge_model="judge/test",
        extractions_path=extractions_path,
        posts=posts,
        output_path=out_path,
        judge_factory=_make_judge_factory(response_map),
    )

    saved = json.loads(out_path.read_text())
    assert saved["judgements"]["model_a"]["p1"]["per_claim"][0]["verdict"] == "exact_match"
    # Empty extractions → judge still called with claims_block="(no claims)" but result is empty per_claim
    assert saved["judgements"]["model_b"]["p1"]["per_claim"] == []


async def test_stage2_skips_post_with_extraction_error(tmp_path):
    extractions_artifact = {
        "metadata": {"extractors": ["model_a"]},
        "extractions": {"model_a": {"p1": [], "p2": []}},
        "errors": {"model_a": {"p1": "RuntimeError: API down"}},
    }
    extractions_path = tmp_path / "extractions.json"
    extractions_path.write_text(json.dumps(extractions_artifact))
    posts = [{"id": "p1", "person_name": "Арестович", "published_at": "2024-01-01", "text": "T"},
             {"id": "p2", "person_name": "Арестович", "published_at": "2024-01-02", "text": "T"}]
    out_path = tmp_path / "judgements.json"

    judge_factory = _make_judge_factory({})

    await run_stage2_judge(
        judge_model="judge/test",
        extractions_path=extractions_path,
        posts=posts,
        output_path=out_path,
        judge_factory=judge_factory,
    )

    saved = json.loads(out_path.read_text())
    # p1 was an error in Stage 1 — judge skips, marker present
    assert saved["judgements"]["model_a"]["p1"].get("skipped_due_to_extraction_error") is True
    # p2 had empty extractions but no error → judge was called
    assert "skipped_due_to_extraction_error" not in saved["judgements"]["model_a"]["p2"]


async def test_stage2_handles_judge_parse_failure(tmp_path):
    extractions_artifact = {
        "metadata": {"extractors": ["model_a"]},
        "extractions": {"model_a": {"p1": [{"claim_text": "X", "prediction_date": None,
                                              "target_date": None, "topic": ""}]}},
        "errors": {"model_a": {}},
    }
    extractions_path = tmp_path / "extractions.json"
    extractions_path.write_text(json.dumps(extractions_artifact))
    posts = [{"id": "p1", "person_name": "Арестович", "published_at": "2024-01-01", "text": "T"}]
    out_path = tmp_path / "judgements.json"

    response_map = {"p1": "this is not valid JSON at all"}

    await run_stage2_judge(
        judge_model="judge/test",
        extractions_path=extractions_path,
        posts=posts,
        output_path=out_path,
        judge_factory=_make_judge_factory(response_map),
    )

    saved = json.loads(out_path.read_text())
    # parse_error logged but per_claim and missed_predictions still present (empty)
    assert saved["judgements"]["model_a"]["p1"]["parse_error"] is not None
    assert saved["judgements"]["model_a"]["p1"]["per_claim"] == []
```

- [ ] **Step 2: Run new tests — verify they fail**

Expected: 3 new tests FAIL — `cannot import name 'run_stage2_judge'`

- [ ] **Step 3: Implement run_stage2_judge**

Append to `scripts/extraction_quality_eval.py`:

```python
from extraction_judge_prompts import JUDGE_SYSTEM, build_judge_prompt, parse_judge_response


async def run_stage2_judge(
    judge_model: str,
    extractions_path: Path,
    posts: list[dict],
    output_path: Path,
    judge_factory: Callable,
    concurrency: int = 1,
    min_call_interval_seconds: float = 0.0,
) -> None:
    """For each (extractor, post, claims) call the judge and save verdicts.

    Posts that errored in Stage 1 are skipped (marked in judgements artifact).
    Judge response parse failures preserve `parse_error` field.
    """
    extractions_artifact = json.loads(extractions_path.read_text(encoding="utf-8"))
    extractions = extractions_artifact["extractions"]
    errors_map = extractions_artifact.get("errors", {})
    posts_by_id = {p["id"]: p for p in posts}

    judge_client = judge_factory(judge_model)
    judgements: dict[str, dict[str, dict]] = {m: {} for m in extractions}

    sem = asyncio.Semaphore(concurrency)

    async def judge_one(model_id: str, post_id: str, claims: list[dict]) -> tuple[str, str, dict]:
        # Skip posts that errored in Stage 1
        if post_id in errors_map.get(model_id, {}):
            return model_id, post_id, {
                "skipped_due_to_extraction_error": True,
                "per_claim": [],
                "missed_predictions": [],
            }

        post = posts_by_id.get(post_id)
        if post is None:
            return model_id, post_id, {
                "skipped_post_not_found": True,
                "per_claim": [],
                "missed_predictions": [],
            }

        prompt = build_judge_prompt(
            post_text=post["text"],
            published_date=post["published_at"],
            extracted_claims=claims,
        )
        async with sem:
            try:
                raw = await judge_client.complete(prompt, system=JUDGE_SYSTEM)
            except Exception as e:
                logger.exception("Judge call failed: %s / %s", model_id, post_id)
                return model_id, post_id, {
                    "judge_error": f"{type(e).__name__}: {e}",
                    "per_claim": [],
                    "missed_predictions": [],
                }
            if min_call_interval_seconds > 0:
                await asyncio.sleep(min_call_interval_seconds)

        parsed = parse_judge_response(raw)
        return model_id, post_id, parsed

    tasks = [
        judge_one(m, pid, claims)
        for m, posts_dict in extractions.items()
        for pid, claims in posts_dict.items()
    ]
    results = await asyncio.gather(*tasks)
    for model_id, post_id, parsed in results:
        judgements[model_id][post_id] = parsed

    # Surface parse_error count to console for visibility (infra signal,
    # not model-quality signal). Aggregator excludes these from gold_agreement.
    parse_error_summary: dict[str, int] = {}
    for model_id, posts_dict in judgements.items():
        n_errors = sum(1 for p in posts_dict.values() if p.get("parse_error"))
        if n_errors > 0:
            parse_error_summary[model_id] = n_errors
    if parse_error_summary:
        logger.warning(
            "Judge parse failures: %s. Excluded from gold_agreement matrix.",
            parse_error_summary,
        )
        print(f"  [stage2] judge parse failures: {parse_error_summary}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "judge": judge_model,
                    "source_extractions": str(extractions_path),
                },
                "judgements": judgements,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run tests — verify all pass**

```bash
.venv/bin/pytest tests/test_extraction_quality_eval.py -v
```

Expected: 21 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction_quality_eval.py tests/test_extraction_quality_eval.py
git commit -m "feat: run_stage2_judge — call Opus per (extractor, post), capture parse errors (Task 13.5 step 5)"
```

**🏁 End of Task 5.** STOP. Report. Wait for "ok"/"next".

---

## Task 6: Stage 3 — run_stage3_aggregate (load judgements + gold, write report)

**Files:**
- Modify: `prediction-tracker/scripts/extraction_quality_eval.py` (add Stage 3)
- Test: `prediction-tracker/tests/test_extraction_quality_eval.py` (add Group B3)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_extraction_quality_eval.py`:

```python
from extraction_quality_eval import run_stage3_aggregate


# =============================================================================
# Group B3 — Stage 3 orchestration (load + aggregate + save)
# =============================================================================


def test_stage3_aggregate_writes_report_with_per_model_section(tmp_path):
    judgements_artifact = {
        "metadata": {"judge": "j/test"},
        "judgements": {
            "model_a": {
                "p1": {
                    "per_claim": [{"verdict": "exact_match"}],
                    "missed_predictions": [],
                }
            }
        },
    }
    judgements_path = tmp_path / "judgements.json"
    judgements_path.write_text(json.dumps(judgements_artifact))

    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps([{"id": "p1", "has_prediction": True}]))

    output_path = tmp_path / "report.json"
    run_stage3_aggregate(
        judgements_path=judgements_path,
        gold_labels_path=gold_path,
        output_path=output_path,
    )

    report = json.loads(output_path.read_text())
    assert "per_model" in report
    assert report["per_model"]["model_a"]["total_claims"] == 1
    assert report["per_model"]["model_a"]["avg_quality_score"] == pytest.approx(3.0)
```

- [ ] **Step 2: Run test — verify fail**

Expected: FAIL — `cannot import name 'run_stage3_aggregate'`

- [ ] **Step 3: Implement run_stage3_aggregate**

Append to `scripts/extraction_quality_eval.py`:

```python
def run_stage3_aggregate(
    judgements_path: Path,
    gold_labels_path: Path,
    output_path: Path,
) -> dict:
    """Load judgements + gold, compute per-model report, save to disk.

    Returns the report dict for in-process use (CLI prints summary table).
    """
    judgements_artifact = json.loads(judgements_path.read_text(encoding="utf-8"))
    judgements = judgements_artifact["judgements"]
    gold_labels = json.loads(gold_labels_path.read_text(encoding="utf-8"))

    report = aggregate_metrics(judgements=judgements, gold_labels=gold_labels)
    report["metadata"] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source_judgements": str(judgements_path),
        "source_gold": str(gold_labels_path),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
```

- [ ] **Step 4: Run tests — verify all pass**

Expected: 22 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction_quality_eval.py tests/test_extraction_quality_eval.py
git commit -m "feat: run_stage3_aggregate — load + aggregate + write report (Task 13.5 step 6)"
```

**🏁 End of Task 6.** STOP. Report. Wait for "ok"/"next".

---

## Task 7: CLI main() — argparse with --stages, --judge, --extractors, --output-dir

**Files:**
- Modify: `prediction-tracker/scripts/extraction_quality_eval.py` (add main + factories)

- [ ] **Step 1: Add CLI dependencies + smoke test**

Append to `tests/test_extraction_quality_eval.py`:

```python
import sys
from io import StringIO

# =============================================================================
# Group C1 — CLI smoke
# =============================================================================


def test_cli_help_lists_stage_argument(capsys):
    """CLI --help mentions --stages, --judge, --extractors."""
    from extraction_quality_eval import _build_arg_parser

    parser = _build_arg_parser()
    out = parser.format_help()
    assert "--stages" in out
    assert "--judge" in out
    assert "--extractors" in out
    assert "--output-dir" in out


def test_cli_parses_stages_csv():
    from extraction_quality_eval import _build_arg_parser, _parse_stages

    args = _build_arg_parser().parse_args(["--stages", "1,3"])
    assert _parse_stages(args.stages) == {1, 3}


def test_cli_parses_extractors_csv():
    from extraction_quality_eval import _build_arg_parser

    args = _build_arg_parser().parse_args(
        ["--extractors", "gemini/x,deepseek/y"]
    )
    assert args.extractors == "gemini/x,deepseek/y"
```

- [ ] **Step 2: Run new tests — verify fail**

Expected: 3 FAIL — `cannot import name '_build_arg_parser'`

- [ ] **Step 3: Implement CLI + entrypoint**

Append to `scripts/extraction_quality_eval.py`:

```python
import argparse
import os
import sys

# Reuse Task 13 factory and constants
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from evaluate_detection import (  # noqa: E402
    _default_extractor_factory,
    PROVIDER_API_KEY_ENV,
    CONCURRENCY_OVERRIDES,
    MIN_CALL_INTERVAL_SECONDS,
    DetectionLLM,
)
from prophet_checker.llm.client import LLMClient  # noqa: E402

PRIMARY_EXTRACTORS = (
    "gemini/gemini-3.1-flash-lite-preview",
    "deepseek/deepseek-chat",
    "anthropic/claude-sonnet-4-6",
)
DEFAULT_JUDGE = "anthropic/claude-opus-4-6"

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_GOLD_PATH = PROJECT_ROOT / "scripts" / "gold_labels.json"
DEFAULT_POSTS_PATH = PROJECT_ROOT / "scripts" / "sample_posts.json"


def _judge_factory(model_id: str):
    """Build LLMClient for the judge model.

    Reuses _default_extractor_factory's provider/key wiring but returns a bare
    LLMClient (no PredictionExtractor wrapper — judge calls .complete directly).
    """
    if "/" not in model_id:
        raise ValueError(f"judge model_id must be 'provider/model', got {model_id}")
    provider, model = model_id.split("/", 1)
    if provider not in PROVIDER_API_KEY_ENV:
        raise ValueError(f"Unknown provider for judge: {provider}")
    api_key = os.environ.get(PROVIDER_API_KEY_ENV[provider])
    if not api_key:
        raise RuntimeError(
            f"Missing API key for judge provider {provider!r}: "
            f"set env var {PROVIDER_API_KEY_ENV[provider]}"
        )
    return LLMClient(provider=provider, model=model, api_key=api_key, temperature=0.0)


def _parse_stages(s: str) -> set[int]:
    return {int(x.strip()) for x in s.split(",") if x.strip()}


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Task 13.5 — Extraction Quality Evaluation (LLM-as-judge)"
    )
    parser.add_argument(
        "--stages",
        default="1,2,3",
        help="Comma-separated stage numbers to run (default: 1,2,3)",
    )
    parser.add_argument(
        "--extractors",
        default=",".join(PRIMARY_EXTRACTORS),
        help="Comma-separated extractor model IDs",
    )
    parser.add_argument("--judge", default=DEFAULT_JUDGE, help="Judge model ID")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "scripts"),
        help="Where to write JSON artifacts",
    )
    parser.add_argument(
        "--gold", default=str(DEFAULT_GOLD_PATH), help="Path to gold_labels.json"
    )
    parser.add_argument(
        "--posts", default=str(DEFAULT_POSTS_PATH), help="Path to sample_posts.json"
    )
    parser.add_argument("--author", default="Арестович", help="Filter posts by person_name")
    return parser


async def _main_async(args: argparse.Namespace) -> None:
    stages = _parse_stages(args.stages)
    out_dir = Path(args.output_dir)
    extractors = [e.strip() for e in args.extractors.split(",") if e.strip()]
    extractions_path = out_dir / "extraction_outputs.json"
    judgements_path = out_dir / "extraction_judgements.json"
    report_path = out_dir / "extraction_eval_report.json"

    if 1 in stages:
        posts = json.loads(Path(args.posts).read_text(encoding="utf-8"))
        print(f"Stage 1: extracting with {len(extractors)} models on {args.author} posts")
        await run_stage1_extraction(
            extractors=extractors,
            posts=posts,
            author_filter=args.author,
            output_path=extractions_path,
            extractor_factory=_default_extractor_factory,
        )
        print(f"  ✓ saved {extractions_path}")

    if 2 in stages:
        posts = json.loads(Path(args.posts).read_text(encoding="utf-8"))
        # Per-judge concurrency override (Opus paid tier supports higher concurrency)
        concurrency = CONCURRENCY_OVERRIDES.get(args.judge, 3)
        min_interval = MIN_CALL_INTERVAL_SECONDS.get(args.judge, 0.0)
        print(f"Stage 2: judging with {args.judge} (concurrency={concurrency})")
        await run_stage2_judge(
            judge_model=args.judge,
            extractions_path=extractions_path,
            posts=posts,
            output_path=judgements_path,
            judge_factory=_judge_factory,
            concurrency=concurrency,
            min_call_interval_seconds=min_interval,
        )
        print(f"  ✓ saved {judgements_path}")

    if 3 in stages:
        print("Stage 3: aggregating metrics")
        report = run_stage3_aggregate(
            judgements_path=judgements_path,
            gold_labels_path=Path(args.gold),
            output_path=report_path,
        )
        _print_report_table(report)
        print(f"  ✓ saved {report_path}")


def _print_report_table(report: dict) -> None:
    print("\n" + "=" * 90)
    print(f"{'Model':<48} {'avg_score':>10} {'hall_rate':>10} {'missed':>8} {'claims':>7}")
    print("-" * 90)
    for m, mr in report["per_model"].items():
        print(
            f"{m:<48} {mr['avg_quality_score']:>10.3f} "
            f"{mr['hallucination_rate']:>10.3f} "
            f"{mr['missed_predictions_count']:>8} "
            f"{mr['total_claims']:>7}"
        )
    print("=" * 90)


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — verify all pass + CLI --help works**

```bash
.venv/bin/pytest tests/test_extraction_quality_eval.py -v
.venv/bin/python scripts/extraction_quality_eval.py --help
```

Expected: 25 tests PASS. Help output shows all CLI flags.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction_quality_eval.py tests/test_extraction_quality_eval.py
git commit -m "feat: CLI orchestrator with --stages flag for selective re-run (Task 13.5 step 7)"
```

**🏁 End of Task 7.** STOP. Report. Wait for "ok"/"next".

---

## Task 8: End-to-end integration test (mocked LLMs, full pipeline)

**Files:**
- Modify: `prediction-tracker/tests/test_extraction_quality_eval.py` (add Group C2)

- [ ] **Step 1: Add integration test**

Append to `tests/test_extraction_quality_eval.py`:

```python
# =============================================================================
# Group C2 — End-to-end pipeline (all 3 stages, mocked LLMs)
# =============================================================================


async def test_full_pipeline_synthetic_data(tmp_path):
    """Stage 1 → Stage 2 → Stage 3 with mocked extractor + judge."""
    posts = [
        {"id": "p1", "person_name": "Арестович", "published_at": "2024-01-01",
         "text": "Контрнаступ почнеться влітку 2023"},
        {"id": "p2", "person_name": "Арестович", "published_at": "2024-01-02",
         "text": "Сьогодні погода гарна"},
    ]
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps([
        {"id": "p1", "has_prediction": True},
        {"id": "p2", "has_prediction": False},
    ]))

    extractions_path = tmp_path / "extraction_outputs.json"
    judgements_path = tmp_path / "extraction_judgements.json"
    report_path = tmp_path / "extraction_eval_report.json"

    # Mock extractor: Gemini extracts 1 claim from p1, none from p2
    claim_map = {
        "model_test": {"p1": ["Контрнаступ почнеться влітку 2023"], "p2": []},
    }
    await run_stage1_extraction(
        extractors=["model_test"],
        posts=posts,
        author_filter="Арестович",
        output_path=extractions_path,
        extractor_factory=_make_factory(claim_map),
    )

    # Mock judge: rates the claim as exact_match
    judge_response = json.dumps({
        "per_claim": [{
            "claim_text": "Контрнаступ почнеться влітку 2023",
            "verdict": "exact_match",
            "reasoning": "Verbatim quote",
        }],
        "missed_predictions": [],
    })
    await run_stage2_judge(
        judge_model="judge/test",
        extractions_path=extractions_path,
        posts=posts,
        output_path=judgements_path,
        judge_factory=_make_judge_factory({"Контрнаступ": judge_response}),
    )

    report = run_stage3_aggregate(
        judgements_path=judgements_path,
        gold_labels_path=gold_path,
        output_path=report_path,
    )

    m = report["per_model"]["model_test"]
    assert m["total_claims"] == 1
    assert m["verdict_distribution"]["exact_match"] == 1
    assert m["avg_quality_score"] == pytest.approx(3.0)
    assert m["gold_agreement"]["gold_YES_with_valid_extraction"] == 1
    assert m["gold_NO_without_valid_extractions"] == 1


async def test_re_run_stage_2_only_uses_existing_extractions(tmp_path):
    """Demonstrates artifact-based re-runs: Stage 1 once, Stage 2 multiple times."""
    posts = [{"id": "p1", "person_name": "Арестович", "published_at": "2024-01-01", "text": "T"}]
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps([{"id": "p1", "has_prediction": True}]))
    extractions_path = tmp_path / "extraction_outputs.json"

    await run_stage1_extraction(
        extractors=["model_a"],
        posts=posts,
        author_filter="Арестович",
        output_path=extractions_path,
        extractor_factory=_make_factory({"model_a": {"p1": ["claim"]}}),
    )

    # Run Stage 2 with judge_v1
    judgements_v1 = tmp_path / "judgements_v1.json"
    await run_stage2_judge(
        judge_model="judge/v1",
        extractions_path=extractions_path,
        posts=posts,
        output_path=judgements_v1,
        judge_factory=_make_judge_factory({"claim": json.dumps({
            "per_claim": [{"claim_text": "claim", "verdict": "exact_match", "reasoning": "v1"}],
            "missed_predictions": [],
        })}),
    )

    # Same Stage 1 artifact, different judge — Stage 1 NOT re-run
    judgements_v2 = tmp_path / "judgements_v2.json"
    await run_stage2_judge(
        judge_model="judge/v2",
        extractions_path=extractions_path,
        posts=posts,
        output_path=judgements_v2,
        judge_factory=_make_judge_factory({"claim": json.dumps({
            "per_claim": [{"claim_text": "claim", "verdict": "hallucination", "reasoning": "v2 disagrees"}],
            "missed_predictions": [],
        })}),
    )

    j1 = json.loads(judgements_v1.read_text())
    j2 = json.loads(judgements_v2.read_text())
    assert j1["judgements"]["model_a"]["p1"]["per_claim"][0]["verdict"] == "exact_match"
    assert j2["judgements"]["model_a"]["p1"]["per_claim"][0]["verdict"] == "hallucination"
```

- [ ] **Step 2: Run new tests — verify they pass without changes (integration of existing code)**

```bash
.venv/bin/pytest tests/test_extraction_quality_eval.py -v
```

Expected: 27 tests PASS. No production code changes needed for these tests — they exercise the existing implementation.

- [ ] **Step 3: Commit**

```bash
git add tests/test_extraction_quality_eval.py
git commit -m "test: end-to-end integration tests for 3-stage pipeline (Task 13.5 step 8)"
```

**🏁 End of Task 8.** STOP. Report. Wait for "ok"/"next".

---

## Task 9: Dry run on 5 posts with real APIs (operational validation)

**Files:**
- Modify: `prediction-tracker/scripts/extraction_quality_eval.py` (add `--limit` flag for subsetting)

- [ ] **Step 1: Add `--limit` CLI flag + subsetting logic**

In `_build_arg_parser()`, add:

```python
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit posts processed (for dry run / debugging)",
    )
```

In `_main_async`, after loading posts:

```python
    if args.limit is not None:
        # Apply author filter first, then limit
        posts = [p for p in posts if p["person_name"] == args.author][: args.limit]
        print(f"  (limit={args.limit}: subset to {len(posts)} posts)")
```

- [ ] **Step 2: Verify env vars present**

```bash
cd prediction-tracker
unset ANTHROPIC_API_KEY OPENAI_API_KEY GEMINI_API_KEY DEEPSEEK_API_KEY  # clear stale
.venv/bin/python -c "
import os
from dotenv import load_dotenv
load_dotenv()
for k in ['ANTHROPIC_API_KEY','OPENAI_API_KEY','GEMINI_API_KEY','DEEPSEEK_API_KEY']:
    v = os.environ.get(k, '')
    print(f'{k}: {bool(v)}')
"
```

Expected: ANTHROPIC, GEMINI, DEEPSEEK = True (Sonnet uses ANTHROPIC; Opus uses ANTHROPIC).

- [ ] **Step 3: Dry run — Stage 1 only, 5 posts**

```bash
unset ANTHROPIC_API_KEY OPENAI_API_KEY GEMINI_API_KEY DEEPSEEK_API_KEY
.venv/bin/python scripts/extraction_quality_eval.py \
    --stages 1 \
    --limit 5 \
    --output-dir /tmp/eval-dry 2>&1 | tail -20
```

Expected: ~3-5 minutes wall (Sonnet + DeepSeek + Gemini concurrent at concurrency=5, throttled where applicable). File `/tmp/eval-dry/extraction_outputs.json` exists with 3 extractor keys, 5 posts each.

Verify:
```bash
.venv/bin/python -c "
import json
e = json.load(open('/tmp/eval-dry/extraction_outputs.json'))
for m, posts in e['extractions'].items():
    n_with_claims = sum(1 for c in posts.values() if c)
    print(f'{m}: {len(posts)} posts, {n_with_claims} with claims, {len(e[\"errors\"][m])} errors')
"
```

- [ ] **Step 4: Dry run — Stage 2 only on Stage 1 output**

```bash
.venv/bin/python scripts/extraction_quality_eval.py \
    --stages 2 \
    --limit 5 \
    --output-dir /tmp/eval-dry 2>&1 | tail -20
```

Expected: ~5 minutes wall (Opus is slower; ~15 judge calls). File `/tmp/eval-dry/extraction_judgements.json` exists.

- [ ] **Step 5: Stage 3 aggregate — verify report is sane**

```bash
.venv/bin/python scripts/extraction_quality_eval.py \
    --stages 3 \
    --limit 5 \
    --output-dir /tmp/eval-dry 2>&1 | tail -15
```

Expected: console table prints, `/tmp/eval-dry/extraction_eval_report.json` shows 3 models with non-zero `total_claims` and `avg_quality_score` between 0 and 3.

- [ ] **Step 6: Commit `--limit` flag**

```bash
git add scripts/extraction_quality_eval.py
git commit -m "feat: --limit flag for dry-run subsetting (Task 13.5 step 9)"
```

**🏁 End of Task 9.** STOP. Report dry-run cost (~$0.50), wall time, sanity-check observations. Wait for "ok"/"next" to proceed to full run.

---

## Task 10: Full eval run — 97 Arestovich posts × 3 extractors × Opus judge

**Files:**
- Generated: `scripts/extraction_outputs.json`, `scripts/extraction_judgements.json`, `scripts/extraction_eval_report.json`
- Update: `prediction-tracker/docs/progress.md`

- [ ] **Step 1: Confirm baseline before run**

```bash
cd prediction-tracker
.venv/bin/pytest tests/ --no-header -q 2>&1 | tail -3
```

Expected: ALL tests pass (Task 13 + Task 13.5).

- [ ] **Step 2: Full run via single command (background)**

Total expected wall: ~2-3 hours. Run in background, monitor.

```bash
unset ANTHROPIC_API_KEY OPENAI_API_KEY GEMINI_API_KEY DEEPSEEK_API_KEY
.venv/bin/python scripts/extraction_quality_eval.py 2>&1 | tee /tmp/eval-full.log
```

Or in stages with verification between:

```bash
# Stage 1 first (~30-60 min)
.venv/bin/python scripts/extraction_quality_eval.py --stages 1 2>&1 | tee /tmp/stage1.log
# verify
.venv/bin/python -c "import json; e=json.load(open('scripts/extraction_outputs.json')); print({m: len(p) for m,p in e['extractions'].items()})"

# Stage 2 (~60-90 min — Opus is slow)
.venv/bin/python scripts/extraction_quality_eval.py --stages 2 2>&1 | tee /tmp/stage2.log

# Stage 3 (instant)
.venv/bin/python scripts/extraction_quality_eval.py --stages 3 2>&1 | tee /tmp/stage3.log
```

- [ ] **Step 3: Verify report and inspect FP/FN sample**

```bash
.venv/bin/python -c "
import json
r = json.load(open('scripts/extraction_eval_report.json'))
for m, mr in r['per_model'].items():
    print(f'\\n=== {m} ===')
    print(f'  total_claims: {mr[\"total_claims\"]}')
    print(f'  avg_quality_score: {mr[\"avg_quality_score\"]}')
    print(f'  hallucination_rate: {mr[\"hallucination_rate\"]}')
    print(f'  verdict_distribution:')
    for v, n in mr['verdict_distribution'].items():
        print(f'    {v}: {n}')
    print(f'  gold_agreement: {mr[\"gold_agreement\"]}')
"
```

- [ ] **Step 4: Update `docs/progress.md`**

Append new section:

```markdown
## Phase 2.5: M2.5 Eval & Data — Task 13.5 Extraction Quality Eval

**Date:** 2026-04-XX
**Models:** Gemini 3.1 Flash Lite, DeepSeek V3.1, Sonnet 4.6 (extractors); Opus 4.6 (judge)
**Dataset:** 97 Arestovich gold-labeled posts
**Cost:** $X.XX actual (vs $14.38 estimated)
**Time:** XX min wall

**Per-model results:**

| Model | avg_quality | hallucination_rate | exact_match | hallucination | not_a_pred |
|---|---:|---:|---:|---:|---:|
| Gemini 3.1 Flash Lite | X.X | X.XX | N | N | N |
| DeepSeek V3.1 | X.X | X.XX | N | N | N |
| Sonnet 4.6 | X.X | X.XX | N | N | N |

**Production decision:** [model X chosen | further iteration needed | etc.]
```

- [ ] **Step 5: Commit results + progress update**

```bash
git add scripts/extraction_outputs.json scripts/extraction_judgements.json \
        scripts/extraction_eval_report.json docs/progress.md
git commit -m "$(cat <<'EOF'
feat: full extraction quality eval — 3 models × 97 posts × Opus judge (Task 13.5)

Cost: $X.XX (vs $14.38 estimated)
Wall: XX min

Top results (avg_quality_score):
  <model>: X.XX (verdict_distribution highlight)
  <model>: X.XX
  <model>: X.XX

Hallucination rates: <model>: X%, <model>: X%, <model>: X%

Production winner: <model> based on F1×quality combined ranking.
Updated docs/progress.md with full numbers and per-model breakdown.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Final test sweep (no regressions)**

```bash
.venv/bin/pytest tests/ --no-header -q 2>&1 | tail -3
```

Expected: ALL tests pass (Task 13's 63 + Task 13.5's 27 = ~90 tests).

**🏁 End of Task 10. END OF TASK 13.5.** STOP. Report final metrics, decision rationale (production model), commit hash. Brainstorm next steps with user (LinkedIn post about extraction eval / Task 14 smoke / M3 pipeline).

---

## Self-Review Notes

**Spec coverage check:**

- ✅ Stage 1 (extraction) — Task 4
- ✅ Stage 2 (judge) — Task 5
- ✅ Stage 3 (aggregate) — Task 6
- ✅ All 3 JSON artifacts — Tasks 4, 5, 6 outputs
- ✅ 6-verdict categorical scoring — Task 1 (VERDICT_VALUES, VERDICT_ORDINAL) + Task 5 prompt
- ✅ Reasoning field per claim — Task 1 JUDGE_SYSTEM template + Task 2 parsed
- ✅ Missed predictions list — Task 1 prompt + Task 5 parsed
- ✅ Gold-blind judge — Task 1 prompt does not include gold label
- ✅ Guideline-aware judge — Task 1 JUDGE_SYSTEM contains 3-criteria + 6-category rubric
- ✅ Blind extractor identity — Task 5 build_judge_prompt does not name model
- ✅ Per-post single-extractor calls — Task 5 loops one (extractor, post) at a time
- ✅ EN instructions, UA/RU content — Task 1 SYSTEM in EN, content untouched
- ✅ Reuse DetectionLLM, factory, CONCURRENCY_OVERRIDES — Task 7 imports
- ✅ CLI with --stages/--judge/--extractors/--output-dir — Task 7
- ✅ Tests in 3 groups (A/B/C) — Tasks 1-3 (A), 4-6 (B), 8 (C)
- ✅ ~10 tests target — actual count: 27 (more than spec target — finer granularity is fine)
- ✅ No production code changes — verified across all tasks; only scripts/ + tests/

**Type consistency:** All function signatures match across tasks (extractor_factory, judge_factory, paths as `Path` objects, dict shapes consistent).

**No placeholders:** All code blocks contain runnable Python. Test assertions use concrete values.

**Risk: Task 9 dry run cost** — ~$0.50 (5 posts × 3 extractors × Opus judge ≈ 15 judge calls × $0.05 each). Worth the cost to validate pipeline before $14 full run.

---

## Handoff

Plan complete and saved to `prediction-tracker/docs/2026-04-21-extraction-quality-eval-plan.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for working through the 10 tasks methodically with checkpoints.

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

Which approach?
