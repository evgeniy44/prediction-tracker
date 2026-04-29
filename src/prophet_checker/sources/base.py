from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator, Protocol

from prophet_checker.models.domain import PersonSource, RawDocument


class Source(Protocol):
    async def collect(
        self,
        person_source: PersonSource,
        since: datetime | None = None,
    ) -> AsyncIterator[RawDocument]:
        ...
