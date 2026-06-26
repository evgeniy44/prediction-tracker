from __future__ import annotations

import hashlib
import random
from typing import Protocol

from prophet_checker.llm.client import LLMClient


class Judge(Protocol):
    id: str

    async def assess(self, prompt: str, *, system: str) -> str: ...


class LLMJudge:
    """Real judge: LLMClient (build with temperature=0). Returns raw text; eval parses it."""

    def __init__(self, llm: LLMClient, judge_id: str) -> None:
        self._llm = llm
        self.id = judge_id

    async def assess(self, prompt: str, *, system: str) -> str:
        return await self._llm.complete(prompt, system=system)


def fingerprint_prompt(text: str) -> str:
    """Stable sha256 of a prompt — pin into EvalMetadata so 'judge said X' is reproducible."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shuffle_options(options: list[str], seed: int) -> list[str]:
    """Deterministic permutation of rubric options (mitigates model-specific position bias)."""
    rng = random.Random(seed)
    shuffled = list(options)
    rng.shuffle(shuffled)
    return shuffled
