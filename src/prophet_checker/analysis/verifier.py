from __future__ import annotations

import logging
from datetime import UTC, datetime

from prophet_checker.llm.prompts import (
    build_verification_prompt,
    get_verification_system,
    parse_verification_response,
)
from prophet_checker.models.domain import Prediction, PredictionStatus

logger = logging.getLogger(__name__)


class PredictionVerifier:
    """Verifies a :class:`Prediction` against known events using an LLM.

    Returns the same prediction object updated with a verdict, confidence
    score, evidence, and ``verified_at`` timestamp.
    """

    def __init__(self, llm_client, confidence_threshold: float = 0.6) -> None:
        self._llm = llm_client
        self._confidence_threshold = confidence_threshold

    async def verify(self, prediction: Prediction) -> Prediction:
        """Ask the LLM to verdict the prediction and return the updated object."""
        prompt = build_verification_prompt(
            claim=prediction.claim_text,
            prediction_date=prediction.prediction_date.isoformat(),
            target_date=(
                prediction.target_date.isoformat() if prediction.target_date else None
            ),
        )

        now = datetime.now(UTC)

        try:
            response = await self._llm.complete(prompt, system=get_verification_system())
            result = parse_verification_response(response)
        except Exception:
            logger.exception("LLM call failed during verification of prediction %s", prediction.id)
            result = None

        if result is None:
            prediction.status = PredictionStatus.UNRESOLVED
            prediction.verified_at = now
            return prediction

        confidence: float = result.get("confidence", 0.0)
        status_str: str = result.get("status", "unresolved")

        if confidence < self._confidence_threshold:
            prediction.status = PredictionStatus.UNRESOLVED
        else:
            try:
                prediction.status = PredictionStatus(status_str)
            except ValueError:
                prediction.status = PredictionStatus.UNRESOLVED

        prediction.confidence = confidence
        prediction.evidence_url = result.get("evidence_url")
        prediction.evidence_text = result.get("evidence_text")
        prediction.verified_at = now

        return prediction
