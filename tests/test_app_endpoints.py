from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from prophet_checker.app import app
from prophet_checker.ingestion import ChannelReport, CycleReport


async def test_health_returns_ok():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_ingest_run_returns_cycle_report():
    orchestrator = MagicMock()
    orchestrator.run_cycle = AsyncMock(return_value=CycleReport(
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        channels_processed=[
            ChannelReport(
                person_source_id="ps1",
                posts_seen=3,
                posts_with_predictions=2,
                predictions_extracted=5,
            ),
        ],
    ))
    app.state.orchestrator = orchestrator

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/ingest/run")

    assert resp.status_code == 200
    body = resp.json()
    assert "channels_processed" in body
    assert "started_at" in body
    assert "finished_at" in body
    assert len(body["channels_processed"]) == 1
    assert body["channels_processed"][0]["person_source_id"] == "ps1"
    assert body["channels_processed"][0]["predictions_extracted"] == 5
