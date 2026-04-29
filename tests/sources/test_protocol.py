from datetime import datetime
from typing import AsyncIterator

from prophet_checker.models.domain import PersonSource, RawDocument
from prophet_checker.sources.base import Source


def test_source_protocol_importable():
    assert Source is not None


def test_source_protocol_has_collect_method():
    assert hasattr(Source, "collect")


class _ConformantImpl:
    async def collect(
        self,
        person_source: PersonSource,
        since: datetime | None = None,
    ) -> AsyncIterator[RawDocument]:
        if False:
            yield


def test_source_protocol_structural_check():
    impl: Source = _ConformantImpl()
    assert impl is not None
