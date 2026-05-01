from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator
from uuid import uuid4

from telethon import TelegramClient

from prophet_checker.models.domain import (
    PersonSource, RawDocument, SourceType,
)


class TelegramSource:
    DEFAULT_MIN_TEXT_LENGTH = 80

    def __init__(
        self,
        client: TelegramClient,
        min_text_length: int = DEFAULT_MIN_TEXT_LENGTH,
    ) -> None:
        self._client = client
        self._min_text_length = min_text_length

    async def collect(
        self,
        person_source: PersonSource,
        since: datetime | None = None,
    ) -> AsyncIterator[RawDocument]:
        if person_source.source_type != SourceType.TELEGRAM:
            return

        channel = person_source.source_identifier
        entity = await self._client.get_entity(channel)

        async for msg in self._client.iter_messages(entity):
            if not msg.text or len(msg.text.strip()) < self._min_text_length:
                continue

            yield RawDocument(
                id=str(uuid4()),
                person_id=person_source.person_id,
                source_type=SourceType.TELEGRAM,
                url=f"https://t.me/{channel}/{msg.id}",
                published_at=msg.date,
                raw_text=msg.text.strip(),
                language="uk",
            )
