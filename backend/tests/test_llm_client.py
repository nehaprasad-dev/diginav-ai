"""Unit tests for LLMClient: successful stream, retry → success, all fail → fallback."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.core.llm_client import LLMClient, GroqError, SCRIPTED_FALLBACK


@pytest.fixture
def client():
    """LLMClient with a fake API key and short timeout for tests."""
    return LLMClient(api_key="test-key", timeout=2.0, max_retries=3)


async def _collect(aiter):
    """Collect all tokens from an async iterator into a string."""
    result = []
    async for token in aiter:
        result.append(token)
    return "".join(result)


class TestSuccessfulStream:
    """When Groq responds successfully, tokens are yielded."""

    @pytest.mark.asyncio
    async def test_streams_tokens_from_groq(self, client):
        """Verify tokens from a successful Groq response are yielded."""
        fake_tokens = ["Hello", " world", "!"]

        async def mock_groq_stream(prompt):
            for t in fake_tokens:
                yield t

        with patch.object(client, "_groq_stream", side_effect=mock_groq_stream):
            result = await _collect(client.stream_narration("test prompt", "name_reserve"))

        assert result == "Hello world!"

    @pytest.mark.asyncio
    async def test_does_not_call_fallback_on_success(self, client):
        """Fallback should not be invoked when Groq succeeds."""
        async def mock_groq_stream(prompt):
            yield "ok"

        fallback_called = False
        original_fallback = client._scripted_fallback

        async def tracking_fallback(step_id):
            nonlocal fallback_called
            fallback_called = True
            async for t in original_fallback(step_id):
                yield t

        with patch.object(client, "_groq_stream", side_effect=mock_groq_stream):
            with patch.object(client, "_scripted_fallback", side_effect=tracking_fallback):
                await _collect(client.stream_narration("test", "name_reserve"))

        assert not fallback_called


class TestRetryThenSuccess:
    """When first attempts fail but a later one succeeds."""

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self, client):
        """After 2 failures, 3rd attempt succeeds."""
        call_count = 0

        async def mock_groq_stream(prompt):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise asyncio.TimeoutError("timeout")
            yield "success"

        # Patch sleep to avoid real delays in tests
        with patch.object(client, "_groq_stream", side_effect=mock_groq_stream):
            with patch("app.core.llm_client.asyncio.sleep", new_callable=AsyncMock):
                result = await _collect(client.stream_narration("test", "din_apply"))

        assert result == "success"
        assert call_count == 3


class TestAllRetriesFailFallback:
    """When all retries fail, scripted fallback is used."""

    @pytest.mark.asyncio
    async def test_falls_back_to_scripted(self, client):
        """After 3 failures, scripted fallback text is returned."""
        async def mock_groq_stream(prompt):
            raise GroqError(500, "server error")
            yield  # make it a generator  # noqa: unreachable

        with patch.object(client, "_groq_stream", side_effect=mock_groq_stream):
            with patch("app.core.llm_client.asyncio.sleep", new_callable=AsyncMock):
                result = await _collect(client.stream_narration("test", "name_reserve"))

        expected = SCRIPTED_FALLBACK["name_reserve"]
        assert result == expected

    @pytest.mark.asyncio
    async def test_fallback_uses_default_for_unknown_step(self, client):
        """Unknown step_id falls back to _default text."""
        async def mock_groq_stream(prompt):
            raise asyncio.TimeoutError()
            yield  # noqa: unreachable

        with patch.object(client, "_groq_stream", side_effect=mock_groq_stream):
            with patch("app.core.llm_client.asyncio.sleep", new_callable=AsyncMock):
                result = await _collect(client.stream_narration("test", "unknown_step"))

        expected = SCRIPTED_FALLBACK["_default"]
        assert result == expected

    @pytest.mark.asyncio
    async def test_fallback_covers_all_three_flows(self, client):
        """Verify scripted fallback exists for key steps in all 3 flows."""
        # Incorporation
        assert "name_reserve" in SCRIPTED_FALLBACK
        assert "cin_gen" in SCRIPTED_FALLBACK
        # GST
        assert "gst_eligibility" in SCRIPTED_FALLBACK
        assert "gst_certificate" in SCRIPTED_FALLBACK
        # SE License
        assert "se_eligibility" in SCRIPTED_FALLBACK
        assert "se_certificate" in SCRIPTED_FALLBACK
