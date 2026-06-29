# scripts/generation/build_generation_gold.py
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from prophet_checker.models.domain import Prediction  # noqa: E402

DATA = PROJECT_ROOT / "scripts" / "data"


def _frozen(pred: Prediction) -> dict:
    # embedding не потрібен генератору/судді й роздуває gold — виключаємо
    return {"prediction": pred.model_dump(mode="json", exclude={"embedding"})}


def build_gold(
    retrieval_gold: list[dict], manual: list[dict], predictions_by_id: dict[str, Prediction]
) -> list[dict]:
    """Pure transform: retrieval-gold + manual + вморожені прогнози → gold records."""
    by_target: dict[str, dict[str, str]] = {}
    for e in retrieval_gold:
        by_target.setdefault(e["target_id"], {})[e["source_field"]] = e["query"]

    out: list[dict] = []
    for i, tid in enumerate(sorted(by_target)):
        phr = by_target[tid]
        prefer = "claim_text" if i % 2 == 0 else "situation"
        other = "situation" if prefer == "claim_text" else "claim_text"
        out.append(
            {
                "id": f"a{i:03d}",
                "question": phr.get(prefer) or phr[other],
                "answerable": True,
                "expected_sources": [_frozen(predictions_by_id[tid])],
                "category": "single_source",
            }
        )

    s = o = 0
    for m in manual:
        answerable = m["category"] == "synthesis"
        if answerable:
            cid, s = f"s{s:03d}", s + 1
            expected = [_frozen(predictions_by_id[p]) for p in m["prediction_ids"]]
        else:
            cid, o = f"o{o:03d}", o + 1
            expected = []
        out.append(
            {
                "id": cid,
                "question": m["question"],
                "answerable": answerable,
                "expected_sources": expected,
                "category": m["category"],
            }
        )
    return out


async def _main() -> None:
    # DB-залежності — локально в entry-point: чиста build_gold лишається легкою для імпорту в тестах
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from prophet_checker.config import Settings
    from prophet_checker.storage.postgres import PostgresPredictionRepository

    retrieval_gold = json.loads((DATA / "retrieval_query_gold.json").read_text(encoding="utf-8"))
    manual = json.loads((DATA / "generation_manual_questions.json").read_text(encoding="utf-8"))

    ids = {e["target_id"] for e in retrieval_gold}
    for m in manual:
        ids.update(m.get("prediction_ids", []))

    settings = Settings()
    engine = create_async_engine(settings.database_url)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        repo = PostgresPredictionRepository(session_factory)
        predictions_by_id = {p.id: p for p in await repo.get_by_ids(sorted(ids))}
    finally:
        await engine.dispose()

    gold = build_gold(retrieval_gold, manual, predictions_by_id)
    out_path = DATA / "generation_gold.json"
    out_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(gold)} cases → {out_path}")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
