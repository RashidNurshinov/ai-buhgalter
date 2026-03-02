"""
Тесты OpenRouter клиента (пункт 1.9.8).

Тестируем:
- OpenRouterClient: chat_completion, chat_completion_with_image
- Retry с exponential backoff
- Fallback на альтернативную модель
- Парсинг ответа (content, tool_calls, usage)
- Оценка стоимости
- ModelConfig, LLMResponse dataclasses
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.openrouter_client import (
    AI_MODELS,
    LLMResponse,
    ModelConfig,
    OpenRouterClient,
    get_openrouter_client,
)


# ─── ModelConfig / LLMResponse ──────────────────────────────


class TestModelConfig:
    """Тесты конфигурации моделей."""

    def test_default_values(self):
        cfg = ModelConfig(
            primary="model-a",
            fallback="model-b",
        )
        assert cfg.temperature == 0.1
        assert cfg.max_tokens == 4096

    def test_custom_values(self):
        cfg = ModelConfig(
            primary="model-a",
            fallback="model-b",
            temperature=0.5,
            max_tokens=8192,
        )
        assert cfg.temperature == 0.5
        assert cfg.max_tokens == 8192

    def test_ai_models_config_has_required_tasks(self):
        """AI_MODELS содержит все необходимые задачи."""
        required_tasks = [
            "agent_reasoning",
            "document_recognition",
            "operation_classification",
            "tax_questions",
            "validation",
        ]
        for task in required_tasks:
            assert task in AI_MODELS, f"Отсутствует задача: {task}"


class TestLLMResponse:
    """Тесты LLMResponse dataclass."""

    def test_default_response(self):
        resp = LLMResponse()
        assert resp.content is None
        assert resp.tool_calls == []
        assert resp.model == ""
        assert resp.tokens_input == 0
        assert resp.tokens_output == 0
        assert resp.cost_usd == 0.0

    def test_response_with_content(self):
        resp = LLMResponse(
            content="Ваш НДС составляет 100 000 руб.",
            model="anthropic/claude-sonnet",
            tokens_input=500,
            tokens_output=200,
            cost_usd=0.0045,
            duration_ms=1200,
            finish_reason="stop",
        )
        assert resp.content == "Ваш НДС составляет 100 000 руб."
        assert resp.duration_ms == 1200

    def test_response_with_tool_calls(self):
        resp = LLMResponse(
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "calculate_taxes",
                        "arguments": '{"year": 2026}',
                    },
                }
            ],
            finish_reason="tool_calls",
        )
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0]["function"]["name"] == "calculate_taxes"


# ─── OpenRouterClient._estimate_cost ────────────────────────


class TestEstimateCost:
    """Тесты оценки стоимости."""

    def test_known_model_cost(self):
        cost = OpenRouterClient._estimate_cost(
            "anthropic/claude-3.5-haiku", 1000, 500
        )
        # haiku: input=0.25/M, output=1.25/M
        expected = (1000 * 0.25 + 500 * 1.25) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_unknown_model_uses_default(self):
        cost = OpenRouterClient._estimate_cost(
            "unknown/model", 1000, 500
        )
        # Default: input=3.0/M, output=15.0/M
        expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_zero_tokens(self):
        cost = OpenRouterClient._estimate_cost(
            "anthropic/claude-sonnet-4-20250514", 0, 0
        )
        assert cost == 0.0


# ─── OpenRouterClient.chat_completion ────────────────────────


class TestChatCompletion:
    """Тесты chat_completion с мокированным HTTP."""

    @pytest.mark.asyncio
    async def test_successful_text_response(self):
        """Успешный текстовый ответ от LLM."""
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "НДС за 1 квартал: 50 000 руб.",
                        "role": "assistant",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 30,
            },
            "model": "anthropic/claude-sonnet-4-20250514",
        }

        client = OpenRouterClient(api_key="test-key")

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response_data
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_http_response)
        mock_http_client.is_closed = False
        client._client = mock_http_client

        result = await client.chat_completion(
            messages=[{"role": "user", "content": "Сколько НДС?"}],
            task="agent_reasoning",
        )

        assert isinstance(result, LLMResponse)
        assert result.content == "НДС за 1 квартал: 50 000 руб."
        assert result.tokens_input == 100
        assert result.tokens_output == 30
        assert result.finish_reason == "stop"
        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_successful_tool_call_response(self):
        """Ответ с tool calls."""
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "calculate_taxes",
                                    "arguments": '{"year": 2026, "quarter": 1}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 200, "completion_tokens": 50},
            "model": "anthropic/claude-sonnet-4-20250514",
        }

        client = OpenRouterClient(api_key="test-key")

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response_data
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_http_response)
        mock_http_client.is_closed = False
        client._client = mock_http_client

        result = await client.chat_completion(
            messages=[{"role": "user", "content": "Рассчитай налоги"}],
            task="agent_reasoning",
            tools=[{"type": "function", "function": {"name": "calculate_taxes"}}],
        )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["function"]["name"] == "calculate_taxes"
        assert result.finish_reason == "tool_calls"

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self):
        """При ошибке primary модели — fallback на альтернативную."""
        import httpx

        client = OpenRouterClient(api_key="test-key")

        call_count = 0
        call_models = []

        async def mock_post(url, json=None, **kwargs):
            nonlocal call_count
            call_count += 1
            call_models.append(json.get("model", "unknown"))

            if call_count <= 3:
                # Первые 3 попытки (retry primary) — ошибка
                mock_resp = MagicMock()
                mock_resp.raise_for_status = MagicMock(
                    side_effect=httpx.HTTPStatusError(
                        "500", request=MagicMock(), response=MagicMock(status_code=500)
                    )
                )
                return mock_resp
            else:
                # Fallback — успех
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    "model": "fallback-model",
                }
                mock_resp.raise_for_status = MagicMock()
                return mock_resp

        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        mock_http_client.is_closed = False
        client._client = mock_http_client

        result = await client.chat_completion(
            messages=[{"role": "user", "content": "test"}],
            task="agent_reasoning",
        )

        assert result.content == "OK"
        # 3 retry на primary + попытки на fallback
        assert call_count >= 4

    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Пустой ответ от API обрабатывается корректно."""
        mock_response_data = {
            "choices": [{}],
            "usage": {},
        }

        client = OpenRouterClient(api_key="test-key")

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response_data
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_http_response)
        mock_http_client.is_closed = False
        client._client = mock_http_client

        result = await client.chat_completion(
            messages=[{"role": "user", "content": "test"}],
        )

        assert result.content is None
        assert result.tool_calls == []
        assert result.tokens_input == 0


# ─── get_openrouter_client singleton ─────────────────────────


class TestGetOpenRouterClient:
    """Тесты фабрики клиента."""

    def test_returns_client(self):
        with patch("app.services.openrouter_client._openrouter_client", None):
            client = get_openrouter_client()
            assert isinstance(client, OpenRouterClient)

    def test_singleton(self):
        with patch("app.services.openrouter_client._openrouter_client", None):
            client1 = get_openrouter_client()
            client2 = get_openrouter_client()
            assert client1 is client2