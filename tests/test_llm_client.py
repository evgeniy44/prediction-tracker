from unittest.mock import AsyncMock, patch
from prophet_checker.llm.client import LLMClient


async def test_llm_client_complete():
    client = LLMClient(provider="openai", model="gpt-4o-mini", api_key="sk-test")
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="Test response"))]

    with patch("prophet_checker.llm.client.acompletion", return_value=mock_response) as mock_call:
        result = await client.complete("Test prompt")
        assert result == "Test response"
        mock_call.assert_called_once()


async def test_llm_client_complete_with_system():
    client = LLMClient(provider="openai", model="gpt-4o-mini", api_key="sk-test")
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="Answer"))]

    with patch("prophet_checker.llm.client.acompletion", return_value=mock_response) as mock_call:
        result = await client.complete("Question", system="You are an analyst")
        assert result == "Answer"
        call_args = mock_call.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are an analyst"
