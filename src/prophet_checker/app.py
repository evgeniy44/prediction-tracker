from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from prophet_checker.config import Settings
from prophet_checker.factory import build_orchestrator
from prophet_checker.ingestion import CycleReport

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    async with AsyncExitStack() as stack:
        orchestrator = await build_orchestrator(settings, stack)
        app.state.orchestrator = orchestrator
        yield


app = FastAPI(title="prediction-tracker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
