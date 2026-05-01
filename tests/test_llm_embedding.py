from unittest.mock import AsyncMock, patch

import pytest

from prophet_checker.llm.embedding import EmbeddingClient


@pytest.mark.asyncio
async def test_embedding_client_default_model():
    client = EmbeddingClient(api_key="test-key")
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.1, 0.2, 0.3])]

    with patch("prophet_checker.llm.embedding.aembedding", return_value=mock_response) as mock_call:
        result = await client.embed("Test text")

    assert result == [0.1, 0.2, 0.3]
    call_kwargs = mock_call.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-3-small"
    assert call_kwargs["api_key"] == "test-key"
    assert call_kwargs["input"] == ["Test text"]


@pytest.mark.asyncio
async def test_embedding_client_custom_model():
    client = EmbeddingClient(model="cohere/embed-english-v3.0", api_key="cohere-key")
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.5] * 1024)]

    with patch("prophet_checker.llm.embedding.aembedding", return_value=mock_response) as mock_call:
        await client.embed("Test")

    assert mock_call.call_args.kwargs["model"] == "cohere/embed-english-v3.0"


@pytest.mark.asyncio
async def test_embedding_client_no_api_key_passes_none():
    client = EmbeddingClient()
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.0])]

    with patch("prophet_checker.llm.embedding.aembedding", return_value=mock_response) as mock_call:
        await client.embed("Test")

    assert mock_call.call_args.kwargs["api_key"] is None
