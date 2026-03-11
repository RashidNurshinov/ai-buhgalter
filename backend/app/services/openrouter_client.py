"""
OpenRouter API Client с поддержкой tool calling.
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 7

Единый клиент для всех LLM-вызовов через OpenRouter.
Поддерживает:
- Chat completion (текст)
- Chat completion с изображениями (vision)
- Tool calling (function calling)
- Fallback-модели
- Retry с exponential backoff
- Логирование токенов и стоимости
"""

import asyncio
import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Конфигурация моделей ──────────────────────────────────


@dataclass
class ModelConfig:
    """Конфигурация модели для конкретной задачи."""
    primary: str
    fallback: str
    temperature: float = 0.1
    max_tokens: int = 4096


# Распределение моделей по задачам (из ТЗ)
AI_MODELS = {
    # Основная логика агента — Qwen 2.5 72B (мощно, недорого)
    "agent_reasoning": ModelConfig(
        primary="qwen/qwen-2.5-72b-instruct",
        fallback="qwen/qwen-2.5-coder-32b-instruct",
        temperature=0.1,
        max_tokens=8192,
    ),
    # Распознавание документов — Qwen 2.5 72B
    "document_recognition": ModelConfig(
        primary="qwen/qwen-2.5-72b-instruct",
        fallback="qwen/qwen-2.5-coder-32b-instruct",
        temperature=0.1,
        max_tokens=4096,
    ),
    # Классификация операций — быстрая модель Qwen 2.5 Coder 32B
    "operation_classification": ModelConfig(
        primary="qwen/qwen-2.5-coder-32b-instruct",
        fallback="meta-llama/llama-3.1-70b-instruct",
        temperature=0.0,
        max_tokens=2048,
    ),
    # Налоговые вопросы — Qwen 2.5 72B
    "tax_questions": ModelConfig(
        primary="qwen/qwen-2.5-72b-instruct",
        fallback="qwen/qwen-2.5-coder-32b-instruct",
        temperature=0.1,
        max_tokens=4096,
    ),
    # Валидация данных — быстрая модель
    "validation": ModelConfig(
        primary="qwen/qwen-2.5-coder-32b-instruct",
        fallback="meta-llama/llama-3.1-70b-instruct",
        temperature=0.0,
        max_tokens=2048,
    ),
}


@dataclass
class LLMResponse:
    """Результат вызова LLM."""
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    finish_reason: str = ""


class OpenRouterClient:
    """
    Клиент для OpenRouter API.
    
    Используется AI Agent Service для всех LLM-вызовов.
    Поддерживает tool calling для агентного цикла.
    """

    BASE_URL = "https://openrouter.ai/api/v1"
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # секунды

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-инициализация HTTP-клиента."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": settings.APP_URL or "https://ai-buhgalter.ru",
                    "X-Title": "AI-Buhgalter",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._client

    async def close(self):
        """Закрыть HTTP-клиент."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ─── Основные методы ──────────────────────────────────

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        task: str = "agent_reasoning",
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict | None = None,
        model_override: str | None = None,
    ) -> LLMResponse:
        """
        Универсальный вызов LLM через OpenRouter.

        Args:
            messages: Список сообщений [{"role": "system", "content": "..."}]
            task: Название задачи (ключ в AI_MODELS)
            tools: Список инструментов для tool calling
            tool_choice: Стратегия выбора tool ("auto", "none", {"type": "function", ...})
            model_override: Принудительно использовать конкретную модель

        Returns:
            LLMResponse с текстом и/или tool_calls
        """
        model_config = AI_MODELS.get(task, AI_MODELS["agent_reasoning"])
        model = model_override or model_config.primary

        # Попробовать primary, при ошибке — fallback
        try:
            return await self._call_with_retry(
                model=model,
                messages=messages,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens,
                tools=tools,
                tool_choice=tool_choice,
            )
        except Exception as e:
            logger.warning(
                "Primary model %s failed: %s. Trying fallback %s",
                model, str(e), model_config.fallback,
            )
            return await self._call_with_retry(
                model=model_config.fallback,
                messages=messages,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens,
                tools=tools,
                tool_choice=tool_choice,
            )

    async def chat_completion_with_image(
        self,
        messages: list[dict[str, Any]],
        image_data: bytes,
        image_media_type: str = "image/jpeg",
        task: str = "document_recognition",
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """
        Вызов LLM с изображением (vision).

        Args:
            messages: Текстовые сообщения
            image_data: Байты изображения
            image_media_type: MIME-тип (image/jpeg, image/png)
            task: Задача
            tools: Инструменты

        Returns:
            LLMResponse
        """
        # Добавляем изображение в последнее user-сообщение
        b64_image = base64.b64encode(image_data).decode("utf-8")
        
        # Формируем multimodal-контент
        enriched_messages = []
        for msg in messages:
            if msg["role"] == "user" and msg is messages[-1]:
                # Последнее user-сообщение → добавляем изображение
                enriched_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image_media_type};base64,{b64_image}"
                            },
                        },
                        {
                            "type": "text",
                            "text": msg.get("content", "Проанализируй это изображение."),
                        },
                    ],
                })
            else:
                enriched_messages.append(msg)

        return await self.chat_completion(
            messages=enriched_messages,
            task=task,
            tools=tools,
        )

    # ─── Внутренние методы ─────────────────────────────────

    async def _call_with_retry(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict | None = None,
    ) -> LLMResponse:
        """Вызов API с retry и exponential backoff."""
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                return await self._make_request(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                )
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "OpenRouter request failed (attempt %d/%d): %s. Retrying in %.1fs",
                        attempt + 1, self.MAX_RETRIES, str(e), delay,
                    )
                    await asyncio.sleep(delay)

        raise last_error or Exception("All retries exhausted")

    async def _make_request(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict | None = None,
    ) -> LLMResponse:
        """Один HTTP-запрос к OpenRouter API."""
        client = await self._get_client()
        start_time = time.monotonic()

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()

        duration_ms = int((time.monotonic() - start_time) * 1000)
        data = response.json()

        # Парсим ответ
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        # Извлекаем tool calls
        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "type": tc.get("type", "function"),
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"].get("arguments", "{}"),
                    },
                })

        result = LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            model=data.get("model", model),
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            cost_usd=self._estimate_cost(
                model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            ),
            duration_ms=duration_ms,
            finish_reason=choice.get("finish_reason", ""),
        )

        logger.info(
            "LLM call: model=%s tokens_in=%d tokens_out=%d cost=$%.6f duration=%dms finish=%s",
            result.model, result.tokens_input, result.tokens_output,
            result.cost_usd, result.duration_ms, result.finish_reason,
        )

        return result

    @staticmethod
    def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Примерная оценка стоимости (USD)."""
        # Цены за 1M токенов (OpenRouter, актуальные на 2026)
        pricing = {
            # Qwen модели — основное (очень недорого)
            "qwen/qwen-2.5-72b-instruct": (0.35, 0.40),
            "qwen/qwen-2.5-coder-32b-instruct": (0.18, 0.22),
            # Llama модели — fallback
            "meta-llama/llama-3.1-70b-instruct": (0.52, 0.75),
            # Anthropic (для сравнения, если кто-то захочет вернуть)
            "anthropic/claude-sonnet-4-20250514": (3.0, 15.0),
            "anthropic/claude-3.5-sonnet": (3.0, 15.0),
            "anthropic/claude-3.5-haiku": (0.25, 1.25),
            "anthropic/claude-opus-4-20250514": (15.0, 75.0),
            # Google
            "google/gemini-2.5-pro-preview": (1.25, 10.0),
        }
        in_price, out_price = pricing.get(model, (0.35, 0.40))
        return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


# Синглтон для использования в приложении
_openrouter_client: OpenRouterClient | None = None


def get_openrouter_client() -> OpenRouterClient:
    """Получить экземпляр OpenRouter клиента."""
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterClient()
    return _openrouter_client