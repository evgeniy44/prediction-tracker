from __future__ import annotations

import random
from collections import defaultdict
from itertools import cycle


def _cell(row: dict) -> tuple[str, str]:
    """Стратифікаційна клітинка: (topic, рік)."""
    year = str(row["prediction_date"])[:4]
    return (row.get("topic", ""), year)


def sample_targets(corpus: list[dict], n: int, seed: int) -> list[dict]:
    """Round-robin по клітинках (topic, рік) для рівномірного покриття; детерміновано по seed."""
    rng = random.Random(seed)
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in corpus:
        cells[_cell(row)].append(row)
    for key in cells:
        cells[key].sort(key=lambda r: r["id"])
        rng.shuffle(cells[key])
    keys = sorted(cells.keys())
    picked: list[dict] = []
    seen: set[str] = set()
    for key in cycle(keys):
        if len(picked) >= n or len(seen) >= len(corpus):
            break
        bucket = cells[key]
        if bucket:
            row = bucket.pop()
            picked.append(row)
            seen.add(row["id"])
    return picked[:n]


_FIELD_LABEL = {
    "claim_text": "ЗМІСТ прогнозу (що саме спрогнозовано)",
    "situation": "ОБСТАВИНИ, за яких зроблено прогноз (період, подія)",
}


def build_query_prompt(row: dict, source_field: str) -> str:
    source_text = row["claim_text"] if source_field == "claim_text" else row["situation"]
    return (
        "Ти формуєш пошуковий запит, який пересічний користувач написав би, щоб знайти прогноз.\n"
        f"Орієнтуйся на {_FIELD_LABEL[source_field]}.\n\n"
        f"Текст-джерело:\n«{source_text}»\n\n"
        "Правила:\n"
        "- одне коротке питання природною українською;\n"
        "- НЕ копіюй характерні слова, числа, назви з джерела дослівно — узагальнюй;\n"
        "- пиши як жива людина, не як цитата.\n\n"
        "Поверни ЛИШЕ текст запиту, без лапок і пояснень."
    )


async def generate_queries(row: dict, llm) -> list[dict]:
    fields = ["claim_text"]
    if (row.get("situation") or "").strip():
        fields.append("situation")
    records = []
    for field in fields:
        query = (await llm.complete(build_query_prompt(row, field))).strip()
        records.append({"query": query, "target_id": row["id"], "source_field": field})
    return records
