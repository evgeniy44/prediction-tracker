#!/usr/bin/env python3
"""
Collect real posts from public Telegram channels via Telethon.

Usage:
    python scripts/collect_telegram_posts.py

First run requires interactive Telegram auth (phone number + code).
Session is saved to scripts/tg_session.session for future runs.

Requires in .env:
    TELEGRAM_API_ID=<id>
    TELEGRAM_API_HASH=<hash>
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from telethon import TelegramClient
from telethon.errors import (
    ChannelInvalidError,
    ChannelPrivateError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)

# ── Config ──────────────────────────────────────────────────────────
CHANNELS = {
    "O_Arestovich_official": "Арестович"
    # "OleksandrZhdanov": "Жданов",
    # "andaboronin": "Піонтковський",
}

POSTS_PER_CHANNEL = 20000      # aim for ~1000 total
MIN_TEXT_LENGTH = 80         # skip very short / media-only posts

# Collect from the very beginning (2012+) up to end of 2025
DATE_FROM = datetime(2012, 1, 1, tzinfo=timezone.utc)
DATE_TO   = datetime(2026, 1, 1, tzinfo=timezone.utc)

# To get even distribution across years we scan the full history
# and sample evenly afterwards
EVEN_SAMPLE = True
OUTPUT = Path(__file__).parent / "data" / "arestovich" / "all.json"
SESSION_PATH = str(Path(__file__).parent / "tg_session")


# ── Main ────────────────────────────────────────────────────────────
async def collect_channel(client: TelegramClient, channel: str, person_name: str) -> list[dict]:
    """Collect ALL text posts from a channel, then sample evenly by year."""
    try:
        entity = await client.get_entity(channel)
    except (ChannelInvalidError, ChannelPrivateError, UsernameInvalidError,
            UsernameNotOccupiedError, ValueError) as e:
        print(f"  ⚠ Cannot access @{channel}: {e}")
        return []

    # Phase 1: scan entire channel history
    all_posts: list[dict] = []
    count = 0
    async for msg in client.iter_messages(entity, offset_date=DATE_TO):
        count += 1
        if msg.date < DATE_FROM:
            break
        if not msg.text or len(msg.text.strip()) < MIN_TEXT_LENGTH:
            continue
        all_posts.append({
            "id": f"{channel}_{msg.id}",
            "person_name": person_name,
            "published_at": msg.date.strftime("%Y-%m-%d"),
            "text": msg.text.strip(),
        })

    print(f"  Scanned {count} messages, found {len(all_posts)} text posts")

    if not EVEN_SAMPLE or len(all_posts) <= POSTS_PER_CHANNEL:
        return all_posts[:POSTS_PER_CHANNEL]

    # Phase 2: even sampling by year
    import random
    random.seed(42)

    by_year: dict[str, list[dict]] = {}
    for p in all_posts:
        year = p["published_at"][:4]
        by_year.setdefault(year, []).append(p)

    years_present = sorted(by_year.keys())
    per_year = max(1, POSTS_PER_CHANNEL // len(years_present))
    sampled: list[dict] = []

    for year in years_present:
        pool = by_year[year]
        take = min(per_year, len(pool))
        sampled.extend(random.sample(pool, take))

    # fill remainder if we're short
    remaining = POSTS_PER_CHANNEL - len(sampled)
    if remaining > 0:
        used_ids = {p["id"] for p in sampled}
        leftover = [p for p in all_posts if p["id"] not in used_ids]
        sampled.extend(random.sample(leftover, min(remaining, len(leftover))))

    sampled.sort(key=lambda p: p["published_at"])
    print(f"  Sampled {len(sampled)} posts across {len(years_present)} years: {', '.join(f'{y}({len(by_year[y])})' for y in years_present)}")
    return sampled


async def main():
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")

    if not api_id or not api_hash:
        print("ERROR: Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")
        sys.exit(1)

    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    await client.start()

    all_posts: list[dict] = []

    for channel, person_name in CHANNELS.items():
        print(f"Collecting from @{channel} ({person_name})...")
        posts = await collect_channel(client, channel, person_name)
        print(f"  Got {len(posts)} text posts")
        all_posts.extend(posts)
        await asyncio.sleep(2)  # gentle rate-limit between channels

    await client.disconnect()

    OUTPUT.write_text(json.dumps(all_posts, ensure_ascii=False, indent=2))

    # ── Summary ─────────────────────────────────────────────────────
    by_person: dict[str, int] = {}
    for p in all_posts:
        by_person[p["person_name"]] = by_person.get(p["person_name"], 0) + 1

    print(f"\n✅ Saved {len(all_posts)} posts to {OUTPUT}")
    print("   By person:")
    for name, count in by_person.items():
        print(f"     {name}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
