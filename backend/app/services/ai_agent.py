"""
AI Agent Service — центральное ядро системы «ИИ-Бухгалтер».
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 3

Реализует цикл: OBSERVE → THINK → ACT → REPORT

Агент:
1. Получает триггер (событие, расписание, вопрос пользователя)
2. Собирает контекст бизнеса
3. Отправляет LLM с инструментами (tool calling)
4. Выполняет tool calls
5. Возвращает LLM результаты (multi-step reasoning)
6. Формирует итоговый отчёт и логирует действия
"""

import json
import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import (
    AgentActionStatus,
    AgentActionType,
    AgentTriggerType,
)
from app.models.agent_action_log import AgentActionLog
from app.models.agent_event import AgentEvent
from app.models.user import User
from app.prompts.agent_system import build_agent_system_prompt, build_event_user_message
from app.services.agent_tools import tool_registry
from app.services.openrouter_client import LLMResponse, get_openrouter_client

logger = logging.getLogger(__name__)

# Максимальное количество итераций tool calling за один цикл агента
MAX_TOOL_ITERATIONS = 15


class AIAgentService:
    """
    Центральный сервис AI-агента.

    Использование:
        agent = AIAgentService(db)

        # По событию (файл загружен)
        result = await agent.handle_event(
            user_id="abc123",
            trigger_type=AgentTriggerType.EVENT_FILE_UPLOADED,
            payload={"files": [{"file_id": "xyz", "filename": "invoice.pdf"}]}
        )

        # Вопрос пользователя (чат)
        result = await agent.handle_event(
            user_id="abc123",
            trigger_type=AgentTriggerType.USER_QUESTION,
            payload={"question": "Сколько я должен по НДС за 1 квартал?"}
        )
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_openrouter_client()

    # ─── Главная точка входа ──────────────────────────────

    async def handle_event(
        self,
        user_id: str,
        trigger_type: AgentTriggerType,
        payload: dict[str, Any] | None = None,
        priority: int = 5,
    ) -> dict[str, Any]:
        """
        Обработать событие через агентный цикл.

        Args:
            user_id: ID пользователя
            trigger_type: Тип триггера
            payload: Данные события
            priority: Приоритет (0=low, 5=normal, 10=critical)

        Returns:
            Результат обработки:
            {
                "event_id": str,
                "summary": str,          # Резюме агента
                "actions": list,          # Список выполненных действий
                "confirmations": list,    # Запрошенные подтверждения
                "tokens_used": int,
                "cost_usd": float,
            }
        """
        payload = payload or {}

        # 1. OBSERVE — Создать событие и собрать контекст
        event = await self._create_event(user_id, trigger_type, payload, priority)

        try:
            # 2. Получить данные пользователя для промпта
            user = await self._get_user(user_id)

            # 3. Построить системный промпт
            system_prompt = self._build_system_prompt(user)

            # 4. Построить user-сообщение из триггера
            user_message = build_event_user_message(trigger_type.value, payload)

            # 5. THINK + ACT — LLM с tool calling (multi-step)
            result = await self._think_and_act(
                event=event,
                user_id=user_id,
                system_prompt=system_prompt,
                user_message=user_message,
            )

            # 6. REPORT — Обновить событие результатами
            event.status = AgentActionStatus.COMPLETED
            event.summary = result["summary"]
            event.tool_calls_count = result["tool_calls_count"]
            event.tokens_used = result["tokens_used"]
            await self.db.commit()

            logger.info(
                "Agent event %s completed: %d tools, %d tokens",
                event.id, result["tool_calls_count"], result["tokens_used"],
            )

            return {
                "event_id": str(event.id),
                "summary": result["summary"],
                "actions": result["actions"],
                "confirmations": result.get("confirmations", []),
                "tokens_used": result["tokens_used"],
                "cost_usd": result["cost_usd"],
            }

        except Exception as e:
            logger.error("Agent event %s failed: %s", event.id, str(e), exc_info=True)
            # Rollback any aborted transaction before updating status
            try:
                await self.db.rollback()
                event.status = AgentActionStatus.FAILED
                event.error_message = str(e)[:500]
                await self.db.commit()
            except Exception:
                logger.error("Failed to update event status after error", exc_info=True)
            raise

    # ─── THINK + ACT: LLM с tool calling ──────────────────

    async def _think_and_act(
        self,
        event: AgentEvent,
        user_id: str,
        system_prompt: str,
        user_message: str,
    ) -> dict[str, Any]:
        """
        Multi-step reasoning: LLM думает, вызывает tools, получает результаты,
        думает снова — пока не решит что всё сделано.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        tools_json = tool_registry.get_tools_for_llm()
        actions: list[dict[str, Any]] = []
        confirmations: list[dict[str, Any]] = []
        total_tokens = 0
        total_cost = 0.0
        step = 0

        for iteration in range(MAX_TOOL_ITERATIONS):
            step += 1

            # Вызов LLM
            llm_response: LLMResponse = await self.llm.chat_completion(
                messages=messages,
                task="agent_reasoning",
                tools=tools_json if tools_json else None,
            )

            total_tokens += llm_response.tokens_input + llm_response.tokens_output
            total_cost += llm_response.cost_usd

            # Если LLM не вызывает tools — это финальный ответ
            if not llm_response.tool_calls:
                # Логируем финальное рассуждение
                await self._log_action_safe(
                    event=event,
                    user_id=user_id,
                    action_type=AgentActionType.AGENT_SUMMARY,
                    step_number=step,
                    agent_reasoning=llm_response.content,
                    tokens_input=llm_response.tokens_input,
                    tokens_output=llm_response.tokens_output,
                    cost_usd=llm_response.cost_usd,
                )

                return {
                    "summary": llm_response.content or "Обработка завершена.",
                    "actions": actions,
                    "confirmations": confirmations,
                    "tool_calls_count": len(actions),
                    "tokens_used": total_tokens,
                    "cost_usd": total_cost,
                }

            # LLM хочет вызвать tools — выполняем
            # Добавляем сообщение assistant с tool_calls в историю
            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if llm_response.content:
                assistant_msg["content"] = llm_response.content
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in llm_response.tool_calls
            ]
            messages.append(assistant_msg)

            # Выполняем каждый tool call
            for tc in llm_response.tool_calls:
                tool_name = tc["function"]["name"]
                tool_args_str = tc["function"]["arguments"]
                tool_args = tool_registry.parse_tool_call_arguments(tool_args_str)
                tool_call_id = tc["id"]

                start_time = time.monotonic()

                # Проверяем, требует ли tool подтверждения
                tool_def = tool_registry.get_tool(tool_name)
                if tool_def and tool_def.requires_confirmation:
                    # Не выполняем, а создаём запрос подтверждения
                    tool_result = {
                        "status": "requires_confirmation",
                        "message": f"Действие '{tool_name}' требует подтверждения пользователя. "
                                   "Запрос подтверждения создан.",
                    }
                else:
                    # Выполняем tool с обработкой DB-ошибок
                    try:
                        tool_result = await tool_registry.execute(
                            tool_name=tool_name,
                            db=self.db,
                            user_id=user_id,
                            _event_id=event.id,
                            **tool_args,
                        )
                    except Exception as tool_exc:
                        # Rollback aborted transaction so we can continue logging
                        logger.error("Tool %s raised exception: %s", tool_name, tool_exc, exc_info=True)
                        try:
                            await self.db.rollback()
                        except Exception:
                            pass
                        tool_result = {
                            "error": True,
                            "error_message": str(tool_exc)[:300],
                            "tool": tool_name,
                        }

                duration_ms = int((time.monotonic() - start_time) * 1000)

                # Определяем тип действия
                action_type = self._map_tool_to_action_type(tool_name)

                # Логируем действие (safe — won't crash on DB errors)
                await self._log_action_safe(
                    event=event,
                    user_id=user_id,
                    action_type=action_type,
                    step_number=step,
                    input_params=tool_args,
                    output_result=tool_result,
                    agent_reasoning=llm_response.content,
                    duration_ms=duration_ms,
                    tokens_input=llm_response.tokens_input,
                    tokens_output=llm_response.tokens_output,
                    cost_usd=llm_response.cost_usd,
                    status=(
                        AgentActionStatus.FAILED
                        if tool_result.get("error")
                        else AgentActionStatus.COMPLETED
                    ),
                )

                actions.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                    "duration_ms": duration_ms,
                })

                # Если это запрос подтверждения — добавляем в список
                if tool_result.get("status") == "confirmation_requested":
                    confirmations.append(tool_result)

                # Добавляем результат tool call в историю сообщений
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                })

        # Если достигли лимита итераций
        logger.warning("Agent reached max iterations (%d) for event %s", MAX_TOOL_ITERATIONS, event.id)
        return {
            "summary": "Обработка прервана: достигнут лимит итераций агента.",
            "actions": actions,
            "confirmations": confirmations,
            "tool_calls_count": len(actions),
            "tokens_used": total_tokens,
            "cost_usd": total_cost,
        }

    # ─── Вспомогательные методы ────────────────────────────

    async def _create_event(
        self,
        user_id: str,
        trigger_type: AgentTriggerType,
        payload: dict[str, Any],
        priority: int,
    ) -> AgentEvent:
        """Создать запись события в БД."""
        event = AgentEvent(
            user_id=user_id,
            trigger_type=trigger_type,
            status=AgentActionStatus.RUNNING,
            priority=priority,
            payload=payload,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def _get_user(self, user_id: str) -> User | None:
        """Получить данные пользователя."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    def _build_system_prompt(self, user: User | None) -> str:
        """Построить системный промпт на основе данных пользователя."""
        if user:
            return build_agent_system_prompt(
                business_name=user.business_name or "",
                inn=user.inn or "",
                tax_system=user.tax_system.value if user.tax_system else "УСН «Доходы минус расходы»",
                region=user.tax_region or "",
                employees_count=user.employee_count or 0,
            )
        return build_agent_system_prompt()

    async def _log_action_safe(
        self,
        event: AgentEvent,
        user_id: str,
        action_type: AgentActionType,
        step_number: int,
        input_params: dict | None = None,
        output_result: dict | None = None,
        agent_reasoning: str | None = None,
        duration_ms: int | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_usd: float = 0.0,
        status: AgentActionStatus = AgentActionStatus.COMPLETED,
        error_message: str | None = None,
    ) -> AgentActionLog | None:
        """Записать действие в лог. Безопасная версия — не падает при DB-ошибках."""
        try:
            log = AgentActionLog(
                user_id=user_id,
                event_id=str(event.id),
                action_type=action_type,
                status=status,
                step_number=step_number,
                input_params=input_params,
                output_result=output_result,
                agent_reasoning=agent_reasoning,
                duration_ms=duration_ms,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost_usd=cost_usd,
                error_message=error_message,
            )
            self.db.add(log)
            await self.db.flush()
            return log
        except Exception as e:
            logger.error("Failed to log action (step %d): %s", step_number, e)
            try:
                await self.db.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def _map_tool_to_action_type(tool_name: str) -> AgentActionType:
        """Маппинг имени tool → AgentActionType для лога."""
        mapping = {
            "get_uploaded_files": AgentActionType.TOOL_GET_FILES,
            "recognize_document": AgentActionType.TOOL_RECOGNIZE_DOCUMENT,
            "parse_xml_document": AgentActionType.TOOL_PARSE_XML,
            "parse_table_file": AgentActionType.TOOL_PARSE_TABLE,
            "classify_operation": AgentActionType.TOOL_CLASSIFY_OPERATION,
            "classify_operations_batch": AgentActionType.TOOL_CLASSIFY_BATCH,
            "match_operation_document": AgentActionType.TOOL_MATCH_OPERATION,
            "detect_duplicates": AgentActionType.TOOL_DETECT_DUPLICATES,
            "detect_anomalies": AgentActionType.TOOL_DETECT_ANOMALIES,
            "calculate_taxes": AgentActionType.TOOL_CALCULATE_TAXES,
            "generate_kudir": AgentActionType.TOOL_GENERATE_KUDIR,
            "generate_purchase_book": AgentActionType.TOOL_GENERATE_PURCHASE_BOOK,
            "generate_sales_book": AgentActionType.TOOL_GENERATE_SALES_BOOK,
            "reconcile_data": AgentActionType.TOOL_RECONCILE,
            "generate_declaration": AgentActionType.TOOL_GENERATE_DECLARATION,
            "validate_declaration": AgentActionType.TOOL_VALIDATE_DECLARATION,
            "get_upcoming_deadlines": AgentActionType.TOOL_GET_CONTEXT,
            "send_notification": AgentActionType.TOOL_SEND_NOTIFICATION,
            "request_user_confirmation": AgentActionType.TOOL_REQUEST_CONFIRMATION,
            "get_business_context": AgentActionType.TOOL_GET_CONTEXT,
            "query_egrul": AgentActionType.TOOL_QUERY_EGRUL,
            "fetch_bank_statements": AgentActionType.TOOL_FETCH_BANK,
            "fetch_ofd_receipts": AgentActionType.TOOL_FETCH_OFD,
            "fetch_edo_documents": AgentActionType.TOOL_FETCH_EDO,
        }
        return mapping.get(tool_name, AgentActionType.AGENT_THINKING)


# ─── Convenience функции ───────────────────────────────────


async def trigger_agent_event(
    db: AsyncSession,
    user_id: str,
    trigger_type: AgentTriggerType,
    payload: dict[str, Any] | None = None,
    priority: int = 5,
) -> dict[str, Any]:
    """
    Convenience-функция для запуска агента.
    Используется из роутеров и Celery-задач.
    """
    agent = AIAgentService(db)
    return await agent.handle_event(
        user_id=user_id,
        trigger_type=trigger_type,
        payload=payload,
        priority=priority,
    )