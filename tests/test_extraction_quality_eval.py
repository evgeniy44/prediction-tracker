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


# =============================================================================
# Group A2 — parse_judge_response
# =============================================================================


from extraction_judge_prompts import parse_judge_response


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
    assert parsed["per_claim"] == []
    assert parsed["missed_predictions"] == []


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


# =============================================================================
# Group A3 — aggregate_metrics
# =============================================================================


from extraction_quality_eval import aggregate_metrics


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
