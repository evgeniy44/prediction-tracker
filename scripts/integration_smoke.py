from __future__ import annotations

import argparse
import asyncio
import sys
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from prophet_checker.config import Settings


EXPECTED_ALEMBIC_HEAD = "edb2e385f26b"


CHECKS = ["postgres", "telegram", "gemini", "openai", "e2e"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="integration_smoke",
        description="Manual smoke test for real Postgres + Telegram + Gemini + OpenAI integration.",
    )
    parser.add_argument(
        "--channel",
        required=True,
        help="Telegram channel username (with or without @)",
    )
    parser.add_argument(
        "--limit",
        required=True,
        type=int,
        help="Max posts to process during e2e cycle. Cost: ~$0.001 × N.",
    )
    parser.add_argument(
        "--component",
        choices=CHECKS,
        default=None,
        help="Run only one stage. Default: run all 5 sequentially.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Don't halt on first fail; run all stages, accumulate errors.",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Drop smoke PersonSource + cascading rows before run.",
    )
    return parser.parse_args()


async def check_postgres(settings: Settings) -> tuple[bool, str]:
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.connect() as conn:
            alembic = await conn.execute(text("SELECT version_num FROM alembic_version"))
            row = alembic.scalar_one_or_none()
            if row != EXPECTED_ALEMBIC_HEAD:
                return False, f"alembic_version is {row!r}, expected {EXPECTED_ALEMBIC_HEAD!r}"

            ext = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname='vector'")
            )
            if ext.scalar_one_or_none() != "vector":
                return False, "pgvector extension not installed"

            return True, "alembic head + pgvector ext OK"
    finally:
        await engine.dispose()


async def main() -> int:
    args = parse_args()
    settings = Settings()

    if args.component in (None, "postgres"):
        t0 = time.perf_counter()
        ok, msg = await check_postgres(settings)
        elapsed = time.perf_counter() - t0
        marker = "✓" if ok else "✗"
        print(f"[1/5] postgres ... {marker} ({elapsed:.2f}s)  {msg}")
        if not ok:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
