"""Збирає held-out вибірку постів для eval: випадковий семпл з корпусу
з виключенням постів, що вже використані в інших наборах.

Вихід — JSON-список [{id, person_name, published_at, text}], готовий для
extraction_quality_eval.py --posts.

Приклад:
    python scripts/extraction/sample_holdout_posts.py \
        -n 100 -o scenarios/11-06-2026-evaluate-extraction/holdout/holdout_posts.json \
        --exclude scenarios/11-06-2026-evaluate-extraction/new/new_input_posts.json \
        --exclude scripts/data/sample_posts.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_SOURCE = PROJECT_ROOT / "scripts" / "data" / "arestovich" / "all.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Held-out вибірка постів з виключенням уже використаних наборів"
    )
    parser.add_argument("-n", "--count", type=int, required=True, help="Скільки постів вибрати")
    parser.add_argument("-o", "--output", required=True, help="Куди писати JSON")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="JSON-файл з постами, чиї id виключити (можна вказувати кілька разів)",
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help=f"Корпус постів (дефолт: {DEFAULT_SOURCE.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=200,
        help="Мінімальна довжина тексту поста в символах (дефолт: 200; 0 — без фільтра)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Seed для відтворюваності (дефолт: 42)"
    )
    args = parser.parse_args()

    posts = json.loads(Path(args.source).read_text(encoding="utf-8"))

    used_ids: set[str] = set()
    for path in args.exclude:
        used_ids |= {p["id"] for p in json.loads(Path(path).read_text(encoding="utf-8"))}

    pool = [
        p for p in posts
        if p["id"] not in used_ids and len(p["text"]) >= args.min_length
    ]
    if len(pool) < args.count:
        parser.error(
            f"у пулі лише {len(pool)} постів після виключень/фільтра — менше за -n {args.count}"
        )

    random.seed(args.seed)
    sample = random.sample(pool, args.count)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"✓ корпус: {len(posts)}, виключено id: {len(used_ids)}, "
        f"пул: {len(pool)}, вибрано: {len(sample)} → {output} (seed={args.seed})"
    )


if __name__ == "__main__":
    main()
