from __future__ import annotations

from litellm import aembedding


class EmbeddingClient:
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        num_retries: int = 3,
    ):
        self._model = model
        self._api_key = api_key
        self._num_retries = num_retries

    async def embed(self, text: str) -> list[float]:
        response = await aembedding(
            model=self._model,
            input=[text],
            api_key=self._api_key,
            num_retries=self._num_retries,
        )
        return response.data[0].embedding
