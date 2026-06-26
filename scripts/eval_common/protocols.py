from __future__ import annotations

from typing import Protocol

from eval_common.models import EvalRun, ScoreCard


class Scorer(Protocol):
    name: str

    async def score(self, run: EvalRun) -> ScoreCard: ...
