"""Будує підмножину постів за списком id у форматі входу extraction_quality_eval.py.

Бере пости з корпусу (дефолт: scripts/data/arestovich/all.json), фільтрує за id
і пише JSON-список [{id, person_name, published_at, text}] — готовий для --posts.

Приклади:
    # id як аргументи
    python scripts/extraction/build_posts_subset.py \
        O_Arestovich_official_312 O_Arestovich_official_7780 \
        -o scripts/data/arestovich/eval_subset.json

    # id з файлу (по одному на рядок або JSON-список)
    python scripts/extraction/build_posts_subset.py \
        --ids-file ids.txt -o scripts/data/arestovich/eval_subset.json

    # файл з голими номерами повідомлень (312, 7780, ...) — префікс додається сам
    python scripts/extraction/build_posts_subset.py \
        --ids-file msg_numbers.txt --prefix O_Arestovich_official_ \
        -o scripts/data/arestovich/eval_subset.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_SOURCE = PROJECT_ROOT / "scripts" / "data" / "arestovich" / "all.json"


def read_ids(args: argparse.Namespace) -> set[str]:
    ids: set[str] = set(args.ids)
    if args.ids_file:
        raw = Path(args.ids_file).read_text(encoding="utf-8").strip()
        if raw.startswith("["):
            ids.update(str(x) for x in json.loads(raw))
        else:
            ids.update(line.strip() for line in raw.splitlines() if line.strip())
    if args.prefix:
        ids = {pid if not pid.isdigit() else f"{args.prefix}{pid}" for pid in ids}
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Підмножина постів за id для extraction_quality_eval.py (--posts)"
    )
    parser.add_argument("ids", nargs="*", help="id постів (напр. O_Arestovich_official_312)")
    parser.add_argument(
        "--ids-file",
        help="Файл з id: по одному на рядок, або JSON-список",
    )
    parser.add_argument(
        "--prefix",
        help="Префікс для голих числових id (напр. O_Arestovich_official_)",
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help=f"Корпус постів (дефолт: {DEFAULT_SOURCE.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument("-o", "--output", required=True, help="Куди писати JSON")
    args = parser.parse_args()

    ids = read_ids(args)
    if not ids:
        parser.error("не задано жодного id (позиційні аргументи або --ids-file)")

    posts = json.loads(Path(args.source).read_text(encoding="utf-8"))
    subset = [p for p in posts if p["id"] in ids]

    missing = ids - {p["id"] for p in subset}
    if missing:
        print(f"⚠ не знайдено в корпусі ({len(missing)}):", file=sys.stderr)
        for pid in sorted(missing):
            print(f"  {pid}", file=sys.stderr)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(subset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    authors = sorted({p["person_name"] for p in subset})
    print(f"✓ {len(subset)}/{len(ids)} постів → {output} (автори: {', '.join(authors)})")


if __name__ == "__main__":
    main()
