"""Малий наскрізний прогін на реальних Postgres+LLM (як scripts/ingestion/integration_smoke.py).
Передумова: docker compose up -d; alembic upgrade head; у БД є верифіковані прогнози.

Usage:
    .venv/bin/python scripts/retrieval/integration_smoke.py --person-id <id> --n 3
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

from retrieval.build_eval_corpus import build  # noqa: E402
from retrieval.build_query_gold import run_gold  # noqa: E402
from retrieval.embed_corpus import run as run_embed  # noqa: E402
from retrieval.retrieval_eval import REPORT_PATH  # noqa: E402


async def smoke(person_id: str, n: int) -> None:
    from prophet_checker.config import Settings
    from prophet_checker.llm import LLMClient

    corpus_path = Path("scripts/data/_smoke_corpus.json")
    gold_path = Path("scripts/data/_smoke_gold.json")

    count = await build(person_id, min_gap_days=14, out_path=corpus_path)
    print(f"[1/3] corpus: {count}")

    settings = Settings()
    llm = LLMClient(
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        api_key=settings.gemini_api_key,
        temperature=0,
    )
    g = await run_gold(corpus_path, gold_path, n=n, seed=1, llm=llm)
    print(f"[2/3] gold: {g}")

    await run_embed(corpus_path, ["text-embedding-3-small"])
    print(f"[3/3] embed done → перевір {REPORT_PATH} після retrieval_eval.main")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--person-id", required=True)
    parser.add_argument("--n", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(smoke(args.person_id, args.n))


if __name__ == "__main__":
    main()
