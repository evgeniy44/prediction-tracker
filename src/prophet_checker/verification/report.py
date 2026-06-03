from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class VerificationEntry(BaseModel):
    prediction_id: str
    status: str | None = None
    error: str | None = None


class VerificationCycleReport(BaseModel):
    started_at: datetime
    finished_at: datetime | None = None
    verified: int = 0
    failed: int = 0
    skipped: int = 0
    entries: list[VerificationEntry] = Field(default_factory=list)
