from __future__ import annotations

from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

EVAL_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS retrieval_eval_emb (
    prediction_id TEXT NOT NULL,
    config        TEXT NOT NULL,
    embedding     vector NOT NULL
)
"""


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


class EvalEmbStore(Protocol):
    async def ensure_table(self) -> None: ...
    async def recreate(self, config: str) -> None: ...
    async def add(self, config: str, prediction_id: str, embedding: list[float]) -> None: ...
    async def search(self, config: str, query: list[float], limit: int) -> list[str]: ...


class PostgresEvalEmbStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def ensure_table(self) -> None:
        async with self._sf() as s:
            await s.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await s.execute(text(EVAL_TABLE_DDL))
            await s.commit()

    async def recreate(self, config: str) -> None:
        async with self._sf() as s:
            await s.execute(text("DELETE FROM retrieval_eval_emb WHERE config = :c"), {"c": config})
            await s.commit()

    async def add(self, config: str, prediction_id: str, embedding: list[float]) -> None:
        async with self._sf() as s:
            await s.execute(
                text(
                    "INSERT INTO retrieval_eval_emb (prediction_id, config, embedding) "
                    "VALUES (:pid, :c, (:emb)::vector)"
                ),
                {"pid": prediction_id, "c": config, "emb": _vec_literal(embedding)},
            )
            await s.commit()

    async def search(self, config: str, query: list[float], limit: int) -> list[str]:
        async with self._sf() as s:
            result = await s.execute(
                text(
                    "SELECT prediction_id FROM retrieval_eval_emb WHERE config = :c "
                    "ORDER BY embedding <=> (:q)::vector LIMIT :k"
                ),
                {"c": config, "q": _vec_literal(query), "k": limit},
            )
            return [r[0] for r in result.all()]
