from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from prophet_checker.config import Settings  # noqa: E402
from prophet_checker.models.domain import (  # noqa: E402
    Prediction,
    PredictionStrength,
    PredictionValue,
)
from prophet_checker.storage.postgres import PostgresPredictionRepository  # noqa: E402

_RANK = {
    PredictionStrength.LOW: 0,
    PredictionStrength.MEDIUM: 1,
    PredictionStrength.HIGH: 2,
}
_VRANK = {
    PredictionValue.LOW: 0,
    PredictionValue.MEDIUM: 1,
    PredictionValue.HIGH: 2,
}


def _score(pred: Prediction) -> int:
    """Сумарний ранг strength+value (0..4). Вищий = вагоміший прогноз."""
    return _RANK[pred.prediction_strength] + _VRANK[pred.prediction_value]


def thin_chronologically(predictions: list[Prediction], min_gap_days: int = 14) -> list[Prediction]:
    """Жадібне проріджування: у кожному вікні [anchor, anchor+gap) лишаємо прогноз із
    найвищим _score (тайбрейк: рання дата, далі id), наступне вікно стартує з kept.date+gap.
    Гарантує: дати лишених прогнозів ≥ min_gap_days одна від одної."""
    ordered = sorted(predictions, key=lambda p: (p.prediction_date, p.id))
    gap = timedelta(days=min_gap_days)
    kept: list[Prediction] = []
    i = 0
    n = len(ordered)
    while i < n:
        anchor = ordered[i].prediction_date
        window_end = anchor + gap
        group = []
        j = i
        while j < n and ordered[j].prediction_date < window_end:
            group.append(ordered[j])
            j += 1
        best = max(group, key=lambda p: (_score(p), -p.prediction_date.toordinal(), p.id))
        kept.append(best)
        next_start = best.prediction_date + gap
        while i < n and ordered[i].prediction_date < next_start:
            i += 1
    return kept


def eligible(pred: Prediction) -> bool:
    """Придатний для корпусу: є strength і value (вихід верифікатора)."""
    return pred.prediction_strength is not None and pred.prediction_value is not None


def prediction_to_row(pred: Prediction) -> dict:
    return {
        "id": pred.id,
        "claim_text": pred.claim_text,
        "situation": pred.situation,
        "topic": pred.topic,
        "prediction_date": pred.prediction_date.isoformat(),
        "strength": pred.prediction_strength.value,
        "value": pred.prediction_value.value,
    }


def write_corpus(predictions: list[Prediction], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [prediction_to_row(p) for p in predictions]
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2))


CORPUS_PATH = Path("scripts/data/retrieval_eval_corpus.json")


async def build(person_id: str, min_gap_days: int, out_path: Path) -> int:
    settings = Settings()
    async with AsyncExitStack() as stack:
        engine = create_async_engine(settings.database_url, echo=False)
        stack.push_async_callback(engine.dispose)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        repo = PostgresPredictionRepository(session_factory)
        predictions = await repo.get_by_person(person_id)
    usable = [p for p in predictions if eligible(p)]
    corpus = thin_chronologically(usable, min_gap_days=min_gap_days)
    write_corpus(corpus, out_path)
    return len(corpus)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--person-id", required=True)
    parser.add_argument("--min-gap-days", type=int, default=14)
    parser.add_argument("--out", type=Path, default=CORPUS_PATH)
    args = parser.parse_args()
    count = asyncio.run(build(args.person_id, args.min_gap_days, args.out))
    print(f"eval corpus: {count} predictions → {args.out}")


if __name__ == "__main__":
    main()
