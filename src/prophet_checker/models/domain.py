from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum

from pydantic import BaseModel


class SourceType(str, Enum):
    TELEGRAM = "telegram"
    NEWS = "news"


class PredictionStatus(str, Enum):
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    UNRESOLVED = "unresolved"


class Person(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: datetime | None = None

    def model_post_init(self, __context) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(UTC)


class PersonSource(BaseModel):
    id: str
    person_id: str
    source_type: SourceType
    source_identifier: str
    enabled: bool = True


class RawDocument(BaseModel):
    id: str
    person_id: str
    source_type: SourceType
    url: str
    published_at: datetime
    raw_text: str
    language: str = "uk"
    collected_at: datetime | None = None

    def model_post_init(self, __context) -> None:
        if self.collected_at is None:
            self.collected_at = datetime.now(UTC)


class Prediction(BaseModel):
    id: str
    document_id: str
    person_id: str
    claim_text: str
    prediction_date: date
    target_date: date | None = None
    topic: str = ""
    status: PredictionStatus = PredictionStatus.UNRESOLVED
    confidence: float = 0.0
    evidence_url: str | None = None
    evidence_text: str | None = None
    verified_at: datetime | None = None
    embedding: list[float] | None = None
