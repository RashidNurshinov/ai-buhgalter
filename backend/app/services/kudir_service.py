"""
Сервис генерации и получения записей КУДиР.
Генерирует записи на основе подтверждённых банковских операций.

Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → services/kudir_service.py
"""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import OperationCategory, OperationStatus
from app.models.bank_operation import BankOperation
from app.models.kudir_entry import KudirEntry


# Категории, которые НЕ являются доходами по УСН
_NON_INCOME_CATEGORIES = frozenset({
    OperationCategory.OWN_FUNDS,
    OperationCategory.INTERNAL_TRANSFER,
    OperationCategory.LOAN_RECEIVED,
})

# Категории, которые НЕ являются расходами по УСН
_NON_EXPENSE_CATEGORIES = frozenset({
    OperationCategory.PERSONAL_WITHDRAWAL,
    OperationCategory.CASH_WITHDRAWAL,
    OperationCategory.INTERNAL_TRANSFER,
})

# Операции в статусах, которые считаем подтверждёнными
_CONFIRMED_STATUSES = (
    OperationStatus.CONFIRMED,
    OperationStatus.RECLASSIFIED,
)


def _quarter_date_range(year: int, quarter: int) -> tuple[datetime.date, datetime.date]:
    """Вернуть (start_date, end_date) для квартала."""
    start_month = (quarter - 1) * 3 + 1
    end_month = quarter * 3
    start_date = datetime.date(year, start_month, 1)
    if end_month == 12:
        end_date = datetime.date(year, 12, 31)
    else:
        end_date = datetime.date(year, end_month + 1, 1) - datetime.timedelta(days=1)
    return start_date, end_date


def _build_doc_ref(op: BankOperation) -> str:
    """Сформировать строку-ссылку на документ для записи КУДиР."""
    parts: list[str] = []
    if op.counterparty_name:
        parts.append(op.counterparty_name[:80])
    parts.append(f"от {op.operation_date.isoformat()}")
    if op.counterparty_inn:
        parts.append(f"ИНН {op.counterparty_inn}")
    return ", ".join(parts) if parts else f"Операция от {op.operation_date.isoformat()}"


class KudirService:
    """Сервис для работы с КУДиР."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Получение записей ──────────────────────────

    async def get_entries(
        self,
        user_id: uuid.UUID,
        year: int,
        quarter: int | None = None,
    ) -> list[KudirEntry]:
        """Получить записи КУДиР за год (и опционально квартал)."""
        conditions = [
            KudirEntry.user_id == str(user_id),
            KudirEntry.year == year,
        ]
        if quarter is not None:
            conditions.append(KudirEntry.quarter == quarter)

        result = await self.db.execute(
            select(KudirEntry)
            .where(and_(*conditions))
            .order_by(KudirEntry.entry_number)
        )
        return list(result.scalars().all())

    async def get_totals(
        self,
        user_id: uuid.UUID,
        year: int,
        quarter: int | None = None,
    ) -> dict:
        """Посчитать итоги КУДиР за период."""
        conditions = [
            KudirEntry.user_id == str(user_id),
            KudirEntry.year == year,
        ]
        if quarter is not None:
            conditions.append(KudirEntry.quarter == quarter)

        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(KudirEntry.income_amount), Decimal("0.00")
                ).label("total_income"),
                func.coalesce(
                    func.sum(KudirEntry.expense_amount), Decimal("0.00")
                ).label("total_expense"),
            ).where(and_(*conditions))
        )
        row = result.one()
        total_income = row.total_income
        total_expense = row.total_expense
        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "net_result": total_income - total_expense,
        }

    # ─── Генерация записей ─────────────────���────────

    async def generate(
        self,
        user_id: uuid.UUID,
        year: int,
        quarter: int | None = None,
        overwrite: bool = False,
    ) -> dict:
        """
        Сгенерировать записи КУДиР на основе подтверждённых банковских операций.

        Логика:
        1. Выбираем подтверждённые операции (CONFIRMED / RECLASSIFIED)
           за указанный год/квартал, где is_income=True или is_expense=True.
        2. Фильтруем «не-доходы» и «не-расходы» по категориям.
        3. Создаём по одной записи КУДиР на каждую подходящую операцию.
        """
        user_id_str = str(user_id)
        quarters = [quarter] if quarter is not None else [1, 2, 3, 4]

        total_created = 0
        total_income = Decimal("0.00")
        total_expense = Decimal("0.00")

        for q in quarters:
            # Удаляем старые записи, если overwrite
            if overwrite:
                await self.db.execute(
                    delete(KudirEntry).where(
                        and_(
                            KudirEntry.user_id == user_id_str,
                            KudirEntry.year == year,
                            KudirEntry.quarter == q,
                        )
                    )
                )
            else:
                # Проверяем, есть ли уже записи → пропускаем квартал
                existing = await self.db.execute(
                    select(func.count(KudirEntry.id)).where(
                        and_(
                            KudirEntry.user_id == user_id_str,
                            KudirEntry.year == year,
                            KudirEntry.quarter == q,
                        )
                    )
                )
                if existing.scalar_one() > 0:
                    continue

            start_date, end_date = _quarter_date_range(year, q)

            # Выбираем подтверждённые операции за квартал
            result = await self.db.execute(
                select(BankOperation)
                .where(
                    and_(
                        BankOperation.user_id == user_id_str,
                        BankOperation.status.in_(_CONFIRMED_STATUSES),
                        BankOperation.operation_date >= start_date,
                        BankOperation.operation_date <= end_date,
                    )
                )
                .order_by(BankOperation.operation_date, BankOperation.created_at)
            )
            operations = result.scalars().all()

            entry_number = 1
            for op in operations:
                income_amount = Decimal("0.00")
                expense_amount = Decimal("0.00")

                if op.is_income and op.category not in _NON_INCOME_CATEGORIES:
                    income_amount = abs(op.amount)

                if op.is_expense and op.category not in _NON_EXPENSE_CATEGORIES:
                    expense_amount = abs(op.amount)

                # Пропускаем, если ни доход, ни расход
                if income_amount == Decimal("0.00") and expense_amount == Decimal("0.00"):
                    continue

                entry = KudirEntry(
                    user_id=user_id_str,
                    entry_number=entry_number,
                    entry_date=op.operation_date,
                    document_ref=_build_doc_ref(op),
                    description=op.purpose or op.counterparty_name or "—",
                    income_amount=income_amount,
                    expense_amount=expense_amount,
                    quarter=q,
                    year=year,
                    linked_operation_id=str(op.id),
                )
                self.db.add(entry)

                total_income += income_amount
                total_expense += expense_amount
                entry_number += 1

            total_created += entry_number - 1

        await self.db.flush()

        return {
            "created_entries": total_created,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_result": total_income - total_expense,
            "year": year,
            "quarter": quarter,
        }