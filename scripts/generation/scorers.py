# scripts/generation/scorers.py
from __future__ import annotations

from eval_common.judge import Judge
from eval_common.models import EvalRun, ScoreCard
from generation.gen_models import (
    CompletenessDetail,
    FaithfulnessDetail,
    RefusalDetail,
    SourceCoverage,
)
from generation.judge_prompts import (
    COMPLETENESS_SYSTEM,
    FAITHFULNESS_SYSTEM,
    REFUSAL_SYSTEM,
    build_completeness_prompt,
    build_faithfulness_prompt,
    build_refusal_prompt,
    parse_completeness_response,
    parse_faithfulness_response,
    parse_refusal_response,
)
from prophet_checker.query.answer_orchestrator import REFUSAL_NO_DATA


class FaithfulnessScorer:
    name = "faithfulness"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    async def score(self, run: EvalRun) -> ScoreCard:
        labels = run.case.labels
        if run.result is None or not labels.answerable:
            return ScoreCard(scorer=self.name, score=None)
        prompt = build_faithfulness_prompt(run.result.answer, run.result.sources)
        raw = await self._judge.assess(prompt, system=FAITHFULNESS_SYSTEM)
        claims = parse_faithfulness_response(raw)
        if not claims:  # відмова / нефактична відповідь → N/A
            return ScoreCard(scorer=self.name, score=None)
        supported = sum(1 for c in claims if c.supported)
        return ScoreCard(
            scorer=self.name,
            score=supported / len(claims),
            detail=FaithfulnessDetail(claims=claims),
        )


class RefusalScorer:
    name = "refusal"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    async def score(self, run: EvalRun) -> ScoreCard:
        labels = run.case.labels
        if run.result is None:
            return ScoreCard(scorer=self.name, score=None)
        answer = run.result.answer
        if answer.strip() == REFUSAL_NO_DATA:
            refused = True
        else:
            raw = await self._judge.assess(build_refusal_prompt(answer), system=REFUSAL_SYSTEM)
            refused = parse_refusal_response(raw)
        correct = (labels.answerable and not refused) or (not labels.answerable and refused)
        return ScoreCard(
            scorer=self.name,
            score=1.0 if correct else 0.0,
            detail=RefusalDetail(
                refused=refused, answerable=labels.answerable, category=labels.category
            ),
        )


class CompletenessScorer:
    name = "completeness"

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    async def score(self, run: EvalRun) -> ScoreCard:
        labels = run.case.labels
        if run.result is None or not labels.answerable or not labels.expected_sources:
            return ScoreCard(scorer=self.name, score=None)
        coverage = []
        for es in labels.expected_sources:
            raw = await self._judge.assess(
                build_completeness_prompt(run.result.answer, es.claim), system=COMPLETENESS_SYSTEM
            )
            covered, reason = parse_completeness_response(raw)
            coverage.append(
                SourceCoverage(prediction_id=es.prediction_id, covered=covered, reason=reason)
            )
        score = sum(1 for c in coverage if c.covered) / len(coverage)
        return ScoreCard(
            scorer=self.name, score=score, detail=CompletenessDetail(coverage=coverage)
        )
