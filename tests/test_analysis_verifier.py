from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from prophet_checker.analysis.verifier import Verifier


def make_split_llm(verdict_raw: str, assessment_raw: str):
    llm = MagicMock()

    def route(prompt, system=None):
        return verdict_raw if "fact-checker" in (system or "") else assessment_raw

    llm.complete = AsyncMock(side_effect=route)
    return llm


VERDICT_JSON = json.dumps({
    "status": "confirmed",
    "confidence": 0.9,
    "prediction_strength": "low",
    "prediction_value": "high",
    "reasoning": "Event occurred as predicted.",
    "evidence": "It happened in June 2023.",
    "retry_after": None,
    "max_horizon": None,
})

ASSESSMENT_JSON = json.dumps({
    "reasoning": "Numeric dated threshold.",
    "prediction_strength": "medium",
    "prediction_value": "low",
})


async def test_verify_merges_verdict_with_assessment_strength():
    llm = make_split_llm(VERDICT_JSON, ASSESSMENT_JSON)
    verifier = Verifier(llm)

    result = await verifier.verify(
        claim="Контрнаступ почнеться влітку 2023",
        situation="Обговорення літньої кампанії",
        prediction_date="2023-01-15",
        target_date="2023-06-01",
        today="2026-05-23",
    )

    assert result["status"] == "confirmed"
    assert result["confidence"] == 0.9
    assert result["prediction_value"] == "high"
    assert result["evidence"] == "It happened in June 2023."
    assert result["prediction_strength"] == "medium"


async def test_verify_fires_both_system_prompts():
    llm = make_split_llm(VERDICT_JSON, ASSESSMENT_JSON)
    verifier = Verifier(llm)

    await verifier.verify(
        claim="c", situation="s", prediction_date="2023-01-15",
        target_date=None, today="2026-05-23",
    )

    systems = [call.kwargs["system"] for call in llm.complete.call_args_list]
    assert any("fact-checker" in s for s in systems)
    assert any("INDEPENDENT axes" in s for s in systems)


async def test_verify_raises_when_assessment_invalid():
    bad_assessment = json.dumps({"prediction_strength": "strong"})
    llm = make_split_llm(VERDICT_JSON, bad_assessment)
    verifier = Verifier(llm)

    with pytest.raises(ValueError, match="invalid prediction_strength"):
        await verifier.verify(
            claim="c", situation="s", prediction_date="2023-01-15",
            target_date=None, today="2026-05-23",
        )
