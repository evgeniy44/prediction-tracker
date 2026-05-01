from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from prophet_checker.ingestion import ChannelReport, CycleReport
from prophet_checker.ingestion.orchestrator import IngestionOrchestrator
from prophet_checker.models.domain import (
    PersonSource,
    Prediction,
    PredictionStatus,
    RawDocument,
    SourceType,
)
from prophet_checker.sources.mock import MockSource
from fakes import FakeSourceRepo, FakePredictionRepo


def _stub_session_factory():
    factory = MagicMock(spec=async_sessionmaker)
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=tx_ctx)
    tx_ctx.__aexit__ = AsyncMock(return_value=None)
    session.begin = MagicMock(return_value=tx_ctx)
    factory.return_value = session
    return factory, session


def _make_extractor(predictions: list[Prediction]):
    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=predictions)
    return extractor


def _make_embedder(vector: list[float] | None = None):
    embedder = MagicMock()
    embedder.embed = AsyncMock(return_value=vector or [0.1] * 1536)
    return embedder


async def test_run_cycle_no_active_sources():
    factory, _ = _stub_session_factory()
    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=FakeSourceRepo(),
        prediction_repo=FakePredictionRepo(),
        extractor=_make_extractor([]),
        embedder=_make_embedder(),
        sources={},
    )

    report = await orchestrator.run_cycle()

    assert isinstance(report, CycleReport)
    assert report.channels_processed == []


async def test_run_cycle_processes_posts_in_one_channel():
    person_source = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    docs = [
        RawDocument(
            id=f"tg:arestovich:{i}",
            person_id="p1",
            source_type=SourceType.TELEGRAM,
            url=f"https://t.me/arestovich/{i}",
            published_at=datetime(2024, 1, 2 + i, tzinfo=UTC),
            raw_text=f"Post {i}",
        )
        for i in range(3)
    ]
    source_repo = FakeSourceRepo()
    await source_repo.save_person_source(person_source)
    prediction_repo = FakePredictionRepo()
    extractor = MagicMock()
    pred = Prediction(
        id="pred-1",
        document_id="x",
        person_id="p1",
        claim_text="claim",
        prediction_date=date(2024, 1, 1),
    )
    extractor.extract = AsyncMock(side_effect=[[pred], [], [pred, pred]])
    embedder = _make_embedder()
    factory, _ = _stub_session_factory()

    orchestrator = IngestionOrchestrator(
        session_factory=factory,
        source_repo=source_repo,
        prediction_repo=prediction_repo,
        extractor=extractor,
        embedder=embedder,
        sources={SourceType.TELEGRAM: MockSource(docs)},
    )

    report = await orchestrator.run_cycle()

    assert len(report.channels_processed) == 1
    ch = report.channels_processed[0]
    assert ch.person_source_id == "ps1"
    assert ch.posts_seen == 3
    assert ch.posts_with_predictions == 2
    assert ch.predictions_extracted == 3
    assert extractor.extract.call_count == 3
    assert embedder.embed.call_count == 3
    assert len(prediction_repo._predictions) == 3
