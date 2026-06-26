from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from eval_common.models import EvalCase


class FakeJudge:
    """Deterministic judge for tests — returns a canned response, ignores the prompt."""

    id = "fake-judge"

    def __init__(self, response: str = "{}") -> None:
        self._response = response

    async def assess(self, prompt: str, *, system: str) -> str:
        return self._response


def fake_sut(result: BaseModel) -> Callable[[EvalCase], Awaitable[BaseModel]]:
    """Return a run_one callable that yields a fixed result regardless of the case."""

    async def _run_one(case: EvalCase) -> BaseModel:
        return result

    return _run_one
