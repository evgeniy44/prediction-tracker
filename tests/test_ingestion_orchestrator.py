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
