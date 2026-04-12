from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from prophet_checker.analysis.verifier import PredictionVerifier
from prophet_checker.models.domain import Prediction, PredictionStatus


def make_prediction(**kwargs) -> Prediction:
    defaults = dict(
        id="pred-1",
        document_id="doc-1",
        person_id="person-1",
        claim_text="Контрнаступ почнеться влітку 2023",
        prediction_date=date(2023, 1, 15),
        target_date=date(2023, 6, 1),
        topic="війна",
    )
    defaults.update(kwargs)
    return Prediction(**defaults)


def make_llm(response: str) -> MagicMock:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=response)
    return llm


async def test_verifier_confirms_prediction():
    llm = make_llm(json.dumps({
        "status": "confirmed",
        "confidence": 0.9,
        "evidence_url": "https://news.com/proof",
        "evidence_text": "The event happened as predicted",
    }))

    verifier = PredictionVerifier(llm_client=llm)
    result = await verifier.verify(make_prediction())

    assert result.status == PredictionStatus.CONFIRMED
    assert result.confidence == 0.9
    assert result.evidence_url == "https://news.com/proof"
    assert result.verified_at is not None


async def test_verifier_refutes_prediction():
    llm = make_llm(json.dumps({
        "status": "refuted",
        "confidence": 0.8,
        "evidence_url": "https://news.com/disproof",
        "evidence_text": "The event did not happen",
    }))

    verifier = PredictionVerifier(llm_client=llm)
    result = await verifier.verify(make_prediction(
        claim_text="Війна закінчиться до кінця 2023",
        target_date=date(2023, 12, 31),
    ))

    assert result.status == PredictionStatus.REFUTED
    assert result.confidence == 0.8


async def test_verifier_marks_low_confidence_as_unresolved():
    llm = make_llm(json.dumps({
        "status": "confirmed",
        "confidence": 0.4,
        "evidence_url": None,
        "evidence_text": "Unclear evidence",
    }))

    verifier = PredictionVerifier(llm_client=llm, confidence_threshold=0.6)
    result = await verifier.verify(make_prediction(claim_text="Something vague", target_date=None))

    assert result.status == PredictionStatus.UNRESOLVED
    assert result.confidence == 0.4


async def test_verifier_handles_invalid_response():
    llm = make_llm("broken json")

    verifier = PredictionVerifier(llm_client=llm)
    result = await verifier.verify(make_prediction())

    assert result.status == PredictionStatus.UNRESOLVED
    assert result.verified_at is not None
