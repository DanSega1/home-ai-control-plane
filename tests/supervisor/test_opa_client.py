"""Tests for supervisor/app/opa_client.py — OPA REST API wrapper."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Patch settings before importing the module under test
with patch("app.config.Settings", autospec=True):
    pass


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a fake settings object so no real .env is needed."""
    monkeypatch.setenv("OPA_URL", "http://opa:8181")


# ---------------------------------------------------------------------------
# evaluate()
# ---------------------------------------------------------------------------


class TestEvaluate:
    @pytest.mark.asyncio
    async def test_returns_true_when_opa_allows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from services.supervisor.app import opa_client

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": True}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            allowed, result = await opa_client.evaluate("homeai/task/allow", {"foo": "bar"})

        assert allowed is True
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_opa_denies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from services.supervisor.app import opa_client

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": False}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            allowed, _ = await opa_client.evaluate("homeai/task/allow", {})

        assert allowed is False

    @pytest.mark.asyncio
    async def test_fails_closed_on_http_error(self) -> None:
        from services.supervisor.app import opa_client

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            allowed, result = await opa_client.evaluate("homeai/task/allow", {})

        # Fail closed — deny when OPA is unreachable
        assert allowed is False
        assert result is None

    @pytest.mark.asyncio
    async def test_result_missing_defaults_to_false(self) -> None:
        from services.supervisor.app import opa_client

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}  # no "result" key

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            allowed, _ = await opa_client.evaluate("homeai/task/allow", {})

        assert allowed is False

    @pytest.mark.asyncio
    async def test_url_built_correctly(self) -> None:
        from services.supervisor.app import opa_client

        captured_url: list[str] = []

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": True}

        async def fake_post(url: str, **kwargs: Any) -> MagicMock:
            captured_url.append(url)
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post

        with patch("httpx.AsyncClient", return_value=mock_client):
            await opa_client.evaluate("homeai/task/allow", {})

        assert captured_url[0].endswith("/v1/data/homeai/task/allow")


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------


class TestConvenienceWrappers:
    @pytest.mark.asyncio
    async def test_check_task_execution_calls_correct_path(self) -> None:
        from services.supervisor.app import opa_client

        with patch.object(opa_client, "evaluate", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = (True, True)
            await opa_client.check_task_execution({"foo": "bar"})
            mock_eval.assert_called_once_with("homeai/task/allow", {"foo": "bar"})

    @pytest.mark.asyncio
    async def test_check_budget_calls_correct_path(self) -> None:
        from services.supervisor.app import opa_client

        with patch.object(opa_client, "evaluate", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = (True, True)
            await opa_client.check_budget({"monthly_tokens_used": 0})
            mock_eval.assert_called_once_with("homeai/budget/allow", {"monthly_tokens_used": 0})

    @pytest.mark.asyncio
    async def test_check_skill_access_calls_correct_path(self) -> None:
        from services.supervisor.app import opa_client

        with patch.object(opa_client, "evaluate", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = (True, True)
            await opa_client.check_skill_access({"skill": "raindrop-io"})
            mock_eval.assert_called_once_with("homeai/skill/allow", {"skill": "raindrop-io"})
