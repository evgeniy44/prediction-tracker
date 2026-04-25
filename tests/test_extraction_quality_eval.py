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
