from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prophet_checker.config import Settings
from prophet_checker.factory import build_orchestrator
from prophet_checker.ingestion import IngestionOrchestrator


def _settings_with_test_env(monkeypatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test")
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "test-hash")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.setenv("TG_SESSION_PATH", "/tmp/test_session")
    return Settings()


async def test_build_orchestrator_returns_orchestrator(monkeypatch):
    settings = _settings_with_test_env(monkeypatch)

    with patch("prophet_checker.factory.TelegramClient") as MockTg:
        mock_tg_instance = MockTg.return_value
        mock_tg_instance.start = AsyncMock()
        mock_tg_instance.disconnect = AsyncMock()

        async with AsyncExitStack() as stack:
            orchestrator = await build_orchestrator(settings, stack)
            assert isinstance(orchestrator, IngestionOrchestrator)


async def test_build_orchestrator_registers_cleanup(monkeypatch):
    settings = _settings_with_test_env(monkeypatch)

    with patch("prophet_checker.factory.TelegramClient") as MockTg:
        mock_tg_instance = MockTg.return_value
        mock_tg_instance.start = AsyncMock()
        mock_tg_instance.disconnect = AsyncMock()

        async with AsyncExitStack() as stack:
            await build_orchestrator(settings, stack)

        mock_tg_instance.disconnect.assert_called_once()
