from __future__ import annotations

import argparse
import asyncio
import sys


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


async def main() -> int:
    args = parse_args()
    print(f"smoke run: channel={args.channel} limit={args.limit} component={args.component or 'all'}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
