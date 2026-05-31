from __future__ import annotations

import asyncio

from prophet_checker.llm.client import LLMClient
from prophet_checker.llm.prompts import (
    build_verification_prompt_v2,
    get_assessment_system_v2,
    get_verification_system_v2,
    parse_assessment_response_v2,
    parse_verification_response_v2,
)


class Verifier:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def verify(
        self,
        claim: str,
        situation: str,
        prediction_date: str,
        target_date: str | None,
        today: str,
    ) -> dict:
        user = build_verification_prompt_v2(
            claim=claim,
            prediction_date=prediction_date,
            target_date=target_date,
            today=today,
            situation=situation,
        )
        verdict_raw, assessment_raw = await asyncio.gather(
            self._llm.complete(user, system=get_verification_system_v2(today)),
            self._llm.complete(user, system=get_assessment_system_v2(today)),
        )
        verdict = parse_verification_response_v2(verdict_raw)
        assessment = parse_assessment_response_v2(assessment_raw)
        verdict["prediction_strength"] = assessment["prediction_strength"]
        return verdict
