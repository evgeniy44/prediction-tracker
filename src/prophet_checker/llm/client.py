from __future__ import annotations

from litellm import acompletion


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        temperature: float = 0.1,
        num_retries: int = 3,
    ):
        self._model = f"{provider}/{model}" if provider != "openai" else model
        self._api_key = api_key
        self._temperature = temperature
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
