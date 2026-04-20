from __future__ import annotations

from litellm import acompletion, aembedding


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        embedding_model: str = "text-embedding-3-small",
        temperature: float = 0.1,
        num_retries: int = 3,
    ):
        # LiteLLM model format: "gpt-4o-mini" for OpenAI, "anthropic/claude-3-5-sonnet" for others
        self._model = f"{provider}/{model}" if provider != "openai" else model
        self._embedding_model = embedding_model
        self._api_key = api_key
        self._temperature = temperature
        # Retries with exponential backoff for transient errors (429, 5xx). LiteLLM
        # handles backoff internally — defaults to 0.5s/1s/2s/4s on consecutive failures.
        self._num_retries = num_retries

    async def complete(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await acompletion(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            api_key=self._api_key,
            num_retries=self._num_retries,
        )
        return response.choices[0].message.content

    async def embed(self, text: str) -> list[float]:
        response = await aembedding(
            model=self._embedding_model,
            input=[text],
            api_key=self._api_key,
            num_retries=self._num_retries,
        )
        return response.data[0].embedding
