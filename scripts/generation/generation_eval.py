# scripts/generation/generation_eval.py
from __future__ import annotations

import argparse
import asyncio
import logging
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path

from eval_common import EvalMetadata, run_eval
from eval_common.clients import build_eval_llm
from eval_common.judge import LLMJudge, fingerprint_prompt
from generation.gold import load_generation_gold
from generation.judge_prompts import COMPLETENESS_SYSTEM, FAITHFULNESS_SYSTEM, REFUSAL_SYSTEM
from generation.metrics import aggregate
from generation.scorers import CompletenessScorer, FaithfulnessScorer, RefusalScorer
from prophet_checker.config import Settings
from prophet_checker.factory import build_answer_orchestrator

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
GOLD_PATH = PROJECT_ROOT / "scripts" / "data" / "generation_gold.json"
OUT_DIR = PROJECT_ROOT / "scripts" / "outputs" / "generation_eval"


async def _main(judge_model: str, limit: int, concurrency: int) -> None:
    settings = Settings()
    cases = load_generation_gold(GOLD_PATH)
    judge = LLMJudge(build_eval_llm(judge_model, temperature=0), judge_id=judge_model)
    scorers = [FaithfulnessScorer(judge), RefusalScorer(judge), CompletenessScorer(judge)]

    metadata = EvalMetadata(
        eval_name="generation",
        created_at=datetime.now(UTC).isoformat(),
        n_cases=len(cases),
        sut_models={
            "generator": "gemini/gemini-3.1-flash-lite-preview",
            "embedder": settings.embedding_model,
        },
        judge_id=judge_model,
        prompt_fingerprints={
            "faithfulness": fingerprint_prompt(FAITHFULNESS_SYSTEM),
            "refusal": fingerprint_prompt(REFUSAL_SYSTEM),
            "completeness": fingerprint_prompt(COMPLETENESS_SYSTEM),
        },
        dataset_path=str(GOLD_PATH),
    )

    async with AsyncExitStack() as stack:
        orchestrator = await build_answer_orchestrator(settings, stack)

        async def run_one(case):
            return await orchestrator.answer(case.input.question, limit=case.input.limit)

        report = await run_eval(
            cases, run_one, scorers, aggregate, metadata, OUT_DIR, concurrency=concurrency
        )

    m = report.metrics
    logger.info(
        "generation eval: n=%d faithfulness=%.3f recall=%.3f refusal_acc=%.3f false_answer=%.3f",
        m.n_total,
        m.faithfulness_mean or 0.0,
        m.recall_mean or 0.0,
        m.refusal_accuracy,
        m.false_answer_rate,
    )
    print(f"report → {OUT_DIR}/report.md  (judge-based, ще не human-calibrated)")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(
        description="Generation eval (faithfulness + refusal + completeness)"
    )
    p.add_argument("--judge", default="anthropic/claude-opus-4-8")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--concurrency", type=int, default=4)
    args = p.parse_args()
    asyncio.run(_main(args.judge, args.limit, args.concurrency))


if __name__ == "__main__":
    main()
