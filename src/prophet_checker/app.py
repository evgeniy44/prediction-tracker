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


@app.post("/ingest/run", response_model=CycleReport)
async def run_ingestion(request: Request) -> CycleReport:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="orchestrator not initialized — server is starting up or shutting down",
        )
    try:
        return await orchestrator.run_cycle()
    except Exception as exc:
        logger.exception("run_cycle failed catastrophically")
        raise HTTPException(
            status_code=500,
            detail=f"unexpected orchestrator failure: {type(exc).__name__}",
        )
