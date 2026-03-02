"""
Тесты AI Agent (пункт 1.15.13).

Тестируем:
- AIAgentService: handle_event (мок LLM)
- Цикл observe → think → act → report
- Tool Registry: регистрация, поиск, выполнение, парсинг аргументов
- Обработка ошибок агента
- Pydantic-схемы агента
- Маппинг tool → AgentActionType
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants.enums import (
    AgentActionStatus,
    AgentActionType,
    AgentConfirmationStatus,
    AgentConfirmationType,
    AgentTriggerType,
)
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentCommandRequest,
    AgentConfirmationOut,
    AgentConfirmationResponse,
    AgentEventOut,
    AgentStatsOut,
)
from app.services.agent_tools import ToolDefinition, ToolRegistry
from app.services.openrouter_client import LLMResponse


# ═══════════════════════════════════════════════════════════════
# ToolRegistry
# ═══════════════════════════════════════════════════════════════


class TestToolRegistry:
    """Тесты реестра инструментов."""

    def test_register_tool_via_decorator(self):
        registry = ToolRegistry()

        @registry.tool(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object", "properties": {}},
            category="test",
        )
        async def handler(db, user_id, **kwargs):
            return {"status": "ok"}

        tool = registry.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"
        assert tool.category == "test"
        assert tool.requires_confirmation is False

    def test_register_tool_via_method(self):
        registry = ToolRegistry()

        async def handler(db, user_id, **kwargs):
            return {"result": True}

        tool = ToolDefinition(
            name="manual_tool",
            description="Manual",
            parameters={},
            handler=handler,
        )
        registry.register(tool)
        assert registry.get_tool("manual_tool") is not None

    def test_get_nonexistent_tool(self):
        registry = ToolRegistry()
        assert registry.get_tool("nonexistent") is None

    def test_get_all_tools(self):
        registry = ToolRegistry()

        @registry.tool(name="t1", description="T1", parameters={})
        async def h1(db, user_id, **kwargs):
            return {}

        @registry.tool(name="t2", description="T2", parameters={})
        async def h2(db, user_id, **kwargs):
            return {}

        assert len(registry.get_all_tools()) == 2

    def test_get_tools_by_category(self):
        registry = ToolRegistry()

        @registry.tool(name="d1", description="D", parameters={}, category="data")
        async def h1(db, user_id, **kwargs):
            return {}

        @registry.tool(name="a1", description="A", parameters={}, category="accounting")
        async def h2(db, user_id, **kwargs):
            return {}

        data_tools = registry.get_tools_by_category("data")
        assert len(data_tools) == 1
        assert data_tools[0].name == "d1"

    def test_get_tools_for_llm_format(self):
        registry = ToolRegistry()

        @registry.tool(
            name="my_tool",
            description="Does something",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
        )
        async def handler(db, user_id, **kwargs):
            return {}

        tools_json = registry.get_tools_for_llm()

        assert len(tools_json) == 1
        assert tools_json[0]["type"] == "function"
        assert tools_json[0]["function"]["name"] == "my_tool"
        assert tools_json[0]["function"]["description"] == "Does something"
        assert "x" in tools_json[0]["function"]["parameters"]["properties"]

    def test_get_tools_for_llm_filter_categories(self):
        registry = ToolRegistry()

        @registry.tool(name="d1", description="D", parameters={}, category="data")
        async def h1(db, user_id, **kwargs):
            return {}

        @registry.tool(name="a1", description="A", parameters={}, category="accounting")
        async def h2(db, user_id, **kwargs):
            return {}

        filtered = registry.get_tools_for_llm(categories=["data"])
        assert len(filtered) == 1
        assert filtered[0]["function"]["name"] == "d1"

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        registry = ToolRegistry()

        @registry.tool(name="add", description="Add", parameters={})
        async def add_handler(db, user_id, **kwargs):
            return {"sum": kwargs.get("a", 0) + kwargs.get("b", 0)}

        mock_db = AsyncMock()
        result = await registry.execute("add", db=mock_db, user_id="user1", a=3, b=5)
        assert result["sum"] == 8

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_raises(self):
        registry = ToolRegistry()
        mock_db = AsyncMock()

        with pytest.raises(ValueError, match="Unknown tool"):
            await registry.execute("nonexistent", db=mock_db, user_id="user1")

    @pytest.mark.asyncio
    async def test_execute_tool_error_returns_error_dict(self):
        registry = ToolRegistry()

        @registry.tool(name="broken", description="Broken", parameters={})
        async def broken_handler(db, user_id, **kwargs):
            raise RuntimeError("Something broke")

        mock_db = AsyncMock()
        result = await registry.execute("broken", db=mock_db, user_id="user1")

        assert result["error"] is True
        assert "Something broke" in result["error_message"]
        assert result["tool"] == "broken"

    def test_parse_tool_call_arguments_valid(self):
        registry = ToolRegistry()
        result = registry.parse_tool_call_arguments('{"year": 2026, "quarter": 1}')
        assert result == {"year": 2026, "quarter": 1}

    def test_parse_tool_call_arguments_invalid(self):
        registry = ToolRegistry()
        result = registry.parse_tool_call_arguments("not json")
        assert result == {}

    def test_parse_tool_call_arguments_empty(self):
        registry = ToolRegistry()
        result = registry.parse_tool_call_arguments("")
        assert result == {}

    def test_requires_confirmation_flag(self):
        registry = ToolRegistry()

        @registry.tool(
            name="dangerous",
            description="Dangerous",
            parameters={},
            requires_confirmation=True,
        )
        async def handler(db, user_id, **kwargs):
            return {}

        tool = registry.get_tool("dangerous")
        assert tool.requires_confirmation is True


# ═══════════════════════════════════════════════════════════════
# Глобальный tool_registry
# ═══════════════════════════════════════════════════════════════


class TestGlobalToolRegistry:
    """Тесты глобального реестра инструментов."""

    def test_global_registry_has_tools(self):
        from app.services.agent_tools import tool_registry

        all_tools = tool_registry.get_all_tools()
        assert len(all_tools) > 0, "Глобальный реестр пуст"

    def test_global_registry_has_key_tools(self):
        from app.services.agent_tools import tool_registry

        expected_names = [
            "get_uploaded_files",
            "get_business_context",
            "calculate_taxes",
            "generate_kudir",
            "classify_operation",
            "get_upcoming_deadlines",
            "generate_declaration",
            "validate_declaration",
            "request_user_confirmation",
        ]
        registered_names = {t.name for t in tool_registry.get_all_tools()}
        for name in expected_names:
            assert name in registered_names, f"Инструмент '{name}' не зарегистрирован"

    def test_global_registry_categories(self):
        from app.services.agent_tools import tool_registry

        categories = {t.category for t in tool_registry.get_all_tools()}
        assert "data" in categories
        assert "accounting" in categories
        assert "notification" in categories


# ═══════════════════════════════════════════════════════════════
# AIAgentService._map_tool_to_action_type
# ═══════════════════════════════════════════════════════════════


class TestToolToActionTypeMapping:
    """Тесты маппинга tool name → AgentActionType."""

    def test_known_mappings(self):
        from app.services.ai_agent import AIAgentService

        cases = {
            "get_uploaded_files": AgentActionType.TOOL_GET_FILES,
            "recognize_document": AgentActionType.TOOL_RECOGNIZE_DOCUMENT,
            "classify_operation": AgentActionType.TOOL_CLASSIFY_OPERATION,
            "calculate_taxes": AgentActionType.TOOL_CALCULATE_TAXES,
            "generate_kudir": AgentActionType.TOOL_GENERATE_KUDIR,
            "generate_declaration": AgentActionType.TOOL_GENERATE_DECLARATION,
            "validate_declaration": AgentActionType.TOOL_VALIDATE_DECLARATION,
            "send_notification": AgentActionType.TOOL_SEND_NOTIFICATION,
            "request_user_confirmation": AgentActionType.TOOL_REQUEST_CONFIRMATION,
            "get_business_context": AgentActionType.TOOL_GET_CONTEXT,
        }
        for tool_name, expected_type in cases.items():
            result = AIAgentService._map_tool_to_action_type(tool_name)
            assert result == expected_type, f"{tool_name} → {result}, ожидали {expected_type}"

    def test_unknown_tool_returns_thinking(self):
        from app.services.ai_agent import AIAgentService

        result = AIAgentService._map_tool_to_action_type("unknown_tool_name")
        assert result == AgentActionType.AGENT_THINKING


# ═══════════════════════════════════════════════════════════════
# Pydantic-схемы агента
# ═══════════════════════════════════════════════════════════════


class TestAgentSchemas:
    """Тесты Pydantic-схем AI Agent."""

    def test_chat_request_valid(self):
        req = AgentChatRequest(message="Сколько я должен заплатить?")
        assert req.message == "Сколько я должен заплатить?"

    def test_chat_request_empty_message(self):
        with pytest.raises(Exception):
            AgentChatRequest(message="")

    def test_chat_request_too_long(self):
        with pytest.raises(Exception):
            AgentChatRequest(message="a" * 5001)

    def test_command_request(self):
        req = AgentCommandRequest(command="Рассчитай налоги за 1 квартал")
        assert "налоги" in req.command

    def test_confirmation_response(self):
        resp = AgentConfirmationResponse(
            confirmation_id="abc123",
            action="confirm",
            user_response="Да, всё верно",
        )
        assert resp.action == "confirm"

    def test_event_out(self):
        out = AgentEventOut(
            id="event-1",
            trigger_type=AgentTriggerType.USER_QUESTION,
            status=AgentActionStatus.COMPLETED,
            priority=5,
            summary="Ответ на вопрос",
            tool_calls_count=2,
            tokens_used=500,
            created_at=datetime.now(timezone.utc),
        )
        assert out.trigger_type == AgentTriggerType.USER_QUESTION
        assert out.tool_calls_count == 2

    def test_chat_response(self):
        resp = AgentChatResponse(
            event_id="evt-1",
            message="НДС за 1 квартал: 50 000 руб.",
            actions=[{"tool": "calculate_taxes", "result": {"vat": "50000"}}],
            tokens_used=800,
            cost_usd=0.005,
        )
        assert resp.message.startswith("НДС")
        assert len(resp.actions) == 1

    def test_stats_out(self):
        stats = AgentStatsOut(
            total_events=100,
            events_today=5,
            total_tool_calls=300,
            total_tokens=50000,
            total_cost_usd=2.50,
            pending_confirmations=3,
        )
        assert stats.total_events == 100
        assert stats.pending_confirmations == 3

    def test_confirmation_out(self):
        out = AgentConfirmationOut(
            id="conf-1",
            confirmation_type=AgentConfirmationType.OPERATION_CLASSIFICATION,
            status=AgentConfirmationStatus.PENDING,
            question="Это оплата за товар?",
            proposed_data={"category": "purchase_goods"},
            options=["Да", "Нет", "Другое"],
            created_at=datetime.now(timezone.utc),
        )
        assert out.status == AgentConfirmationStatus.PENDING
        assert len(out.options) == 3


# ═══════════════════════════════════════════════════════════════
# AIAgentService.handle_event (с мокированным LLM)
# ═══════════════════════════════════════════════════════════════


class TestAIAgentServiceHandleEvent:
    """Тесты цикла агента с замоканным LLM."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def test_user(self):
        user = MagicMock()
        user.id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        user.email = "test@example.com"
        user.full_name = "Тест"
        user.inn = "1234567890"
        user.business_name = "ИП Тест"
        user.tax_system = MagicMock()
        user.tax_system.value = "usn_income_expense"
        user.tax_region = "56"
        user.employee_count = 0
        return user

    @pytest.mark.asyncio
    async def test_handle_question_no_tools(self, mock_db, test_user):
        """Агент отвечает на вопрос без tool calls (одна итерация)."""
        # Мок: get_user возвращает test_user
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = mock_user_result

        # Мок LLM: текстовый ответ без tool calls
        mock_llm_response = LLMResponse(
            content="Ваш НДС за 1 квартал составит примерно 50 000 руб.",
            tool_calls=[],
            model="anthropic/claude-sonnet",
            tokens_input=200,
            tokens_output=50,
            cost_usd=0.003,
            finish_reason="stop",
        )

        with patch("app.services.ai_agent.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat_completion = AsyncMock(return_value=mock_llm_response)
            mock_get_client.return_value = mock_client

            from app.services.ai_agent import AIAgentService

            agent = AIAgentService(mock_db)

            result = await agent.handle_event(
                user_id=str(test_user.id),
                trigger_type=AgentTriggerType.USER_QUESTION,
                payload={"question": "Сколько НДС за 1 квартал?"},
            )

        assert "summary" in result
        assert result["tokens_used"] > 0
        assert len(result["actions"]) == 0  # Без tool calls

    @pytest.mark.asyncio
    async def test_handle_event_with_tool_call(self, mock_db, test_user):
        """Агент вызывает tool, получает результат, формирует ответ."""
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = mock_user_result

        # Первый LLM-вызов: tool call
        llm_response_1 = LLMResponse(
            content=None,
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "get_upcoming_deadlines",
                    "arguments": '{"days_ahead": 30}',
                },
            }],
            model="claude-sonnet",
            tokens_input=150,
            tokens_output=30,
            cost_usd=0.001,
            finish_reason="tool_calls",
        )

        # Второй LLM-вызов: финальный ответ
        llm_response_2 = LLMResponse(
            content="У вас 3 ближайших дедлайна в апреле.",
            tool_calls=[],
            model="claude-sonnet",
            tokens_input=250,
            tokens_output=40,
            cost_usd=0.002,
            finish_reason="stop",
        )

        call_count = 0

        async def mock_chat_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return llm_response_1
            return llm_response_2

        with patch("app.services.ai_agent.get_openrouter_client") as mock_get_client, \
             patch("app.services.ai_agent.tool_registry") as mock_registry:

            mock_client = AsyncMock()
            mock_client.chat_completion = mock_chat_completion
            mock_get_client.return_value = mock_client

            # Мок tool registry
            mock_registry.get_tools_for_llm.return_value = [
                {"type": "function", "function": {"name": "get_upcoming_deadlines"}}
            ]
            mock_registry.parse_tool_call_arguments.return_value = {"days_ahead": 30}
            mock_registry.get_tool.return_value = MagicMock(requires_confirmation=False)
            mock_registry.execute = AsyncMock(return_value={
                "status": "ok",
                "upcoming_count": 3,
                "upcoming_events": [
                    {"title": "НДС 1/3", "deadline": "2026-04-27"},
                ],
            })

            from app.services.ai_agent import AIAgentService

            agent = AIAgentService(mock_db)

            result = await agent.handle_event(
                user_id=str(test_user.id),
                trigger_type=AgentTriggerType.USER_QUESTION,
                payload={"question": "Какие ближайшие дедлайны?"},
            )

        assert result["summary"] == "У вас 3 ближайших дедлайна в апреле."
        assert len(result["actions"]) == 1
        assert result["actions"][0]["tool"] == "get_upcoming_deadlines"
        assert result["tokens_used"] > 0

    @pytest.mark.asyncio
    async def test_handle_event_error(self, mock_db, test_user):
        """Ошибка LLM → событие получает статус FAILED."""
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = mock_user_result

        with patch("app.services.ai_agent.get_openrouter_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat_completion = AsyncMock(
                side_effect=RuntimeError("LLM unavailable")
            )
            mock_get_client.return_value = mock_client

            from app.services.ai_agent import AIAgentService

            agent = AIAgentService(mock_db)

            with pytest.raises(RuntimeError, match="LLM unavailable"):
                await agent.handle_event(
                    user_id=str(test_user.id),
                    trigger_type=AgentTriggerType.USER_QUESTION,
                    payload={"question": "тест"},
                )

        # Проверяем, что commit вызывался (для сохранения ошибки)
        mock_db.commit.assert_called()


# ═══════════════════════════════════════════════════════════════
# trigger_agent_event convenience function
# ═══════════════════════════════════════════════════════════════


class TestTriggerAgentEvent:
    """Тесты convenience-функции trigger_agent_event."""

    @pytest.mark.asyncio
    async def test_trigger_creates_agent_and_calls_handle(self):
        with patch("app.services.ai_agent.AIAgentService") as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.handle_event = AsyncMock(return_value={
                "event_id": "test",
                "summary": "OK",
            })
            MockAgent.return_value = mock_instance

            from app.services.ai_agent import trigger_agent_event

            mock_db = AsyncMock()
            result = await trigger_agent_event(
                db=mock_db,
                user_id="user-1",
                trigger_type=AgentTriggerType.SCHEDULE_DAILY,
                payload={"test": True},
            )

            assert result["summary"] == "OK"
            mock_instance.handle_event.assert_called_once()