"""Будує набір для ручної оцінки екстракції: 50 постів з передбаченнями (з БД) +
50 без (точковий прогін extractor на all.json) → JSON з порожніми score/note."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from prophet_checker.analysis.extractor import PredictionExtractor  # noqa: E402
from prophet_checker.config import Settings  # noqa: E402
from prophet_checker.llm.client import LLMClient  # noqa: E402
from prophet_checker.models.db import PredictionDB, RawDocumentDB  # noqa: E402

ALL_POSTS = PROJECT_ROOT / "scripts" / "data" / "arestovich" / "all.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "scripts" / "outputs" / "annotation" / "annotation_set.json"
DEFAULT_MODEL = "gemini/gemini-3.1-flash-lite-preview"

PROVIDER_API_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def post_url(post_id: str) -> str:
    if post_id.startswith("tg:"):
        channel, _, msg = post_id[3:].rpartition(":")
    else:
        channel, _, msg = post_id.rpartition("_")
    return f"https://t.me/{channel.lstrip('@')}/{msg}"


def _claim_entry(p) -> dict:
    return {
        "claim_text": p.claim_text,
        "situation": p.situation,
        "prediction_date": p.prediction_date.isoformat() if p.prediction_date else None,
        "target_date": p.target_date.isoformat() if p.target_date else None,
        "topic": p.topic,
        "claim_score": None,
        "claim_note": "",
    }


def _post_entry(post_id: str, published_at, has_predictions: bool, source: str, claims: list) -> dict:
    return {
        "post_id": post_id,
        "url": post_url(post_id),
        "published_at": published_at,
        "has_predictions": has_predictions,
        "source": source,
        "post_score": None,
        "post_note": "",
        "claims": claims,
    }


async def load_db_positives(session_factory, n: int, min_chars: int, seed: int) -> list[dict]:
    async with session_factory() as session:
        docs = (await session.execute(
            select(RawDocumentDB)
            .where(func.length(RawDocumentDB.raw_text) >= min_chars)
            .where(RawDocumentDB.id.in_(select(PredictionDB.document_id).distinct()))
        )).scalars().all()
        chosen = random.Random(seed).sample(list(docs), min(n, len(docs)))
        result = []
        for doc in chosen:
            preds = (await session.execute(
                select(PredictionDB).where(PredictionDB.document_id == doc.id)
            )).scalars().all()
            published = doc.published_at.date().isoformat() if doc.published_at else None
            result.append(_post_entry(doc.id, published, True, "db", [_claim_entry(p) for p in preds]))
        return result
