"""
Сервис генерации и получения записей книги покупок.
Генерирует записи на основе подтверждённых входящих документов с НДС.

Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → services/purchase_book_service.py
"""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.enums import DocumentStatus, DocumentType
from app.models.book_entry import PurchaseBookEntry
from app.models.document import Document


# Типы документов, попадающие в книгу покупок (входящие с НДС)
_PURCHASE_DOC_TYPES = (
    DocumentType.INVOICE,
    DocumentType.UPD,
    DocumentType.TORG12,
    DocumentType.ACT,
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


class PurchaseBookService:
    """Сервис для работы с книгой покупок."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Получение записей ──────────────────────────

    async def get_entries(
        self,
        user_id: uuid.UUID,
        year: int,
        quarter: int,
    ) -> list[PurchaseBookEntry]:
        """Получить записи книги покупок за квартал."""
        from sqlalchemy.orm import selectinload
        
        result = await self.db.execute(
            select(PurchaseBookEntry)
            .options(selectinload(PurchaseBookEntry.counterparty))
            .where(
                and_(
                    PurchaseBookEntry.user_id == str(user_id),
                    PurchaseBookEntry.year == year,
                    PurchaseBookEntry.quarter == quarter,
                )
            )
            .order_by(PurchaseBookEntry.entry_number)
        )
        return list(result.scalars().all())

    async def get_totals(
        self,
        user_id: uuid.UUID,
        year: int,
        quarter: int,
    ) -> dict:
        """Посчитать итоги книги покупок за квартал."""
        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(PurchaseBookEntry.total_without_vat), Decimal("0.00")
                ).label("total_without_vat"),
                func.coalesce(
                    func.sum(PurchaseBookEntry.vat_amount), Decimal("0.00")
                ).label("total_vat"),
                func.coalesce(
                    func.sum(PurchaseBookEntry.total_with_vat), Decimal("0.00")
                ).label("total_with_vat"),
            ).where(
                and_(
                    PurchaseBookEntry.user_id == str(user_id),
                    PurchaseBookEntry.year == year,
                    PurchaseBookEntry.quarter == quarter,
                )
            )
        )
        row = result.one()
        return {
            "total_without_vat": row.total_without_vat,
            "total_vat": row.total_vat,
            "total_with_vat": row.total_with_vat,
        }

    # ─── Генерация записей ──────────────────────────

    async def generate(
        self,
        user_id: uuid.UUID,
        year: int,
        quarter: int,
        overwrite: bool = False,
    ) -> dict:
        """
        Сгенерировать записи книги покупок на основе подтверждённых
        входящих документов (счёт-фактура, УПД, ТОРГ-12, акт) с НДС.

        Логика:
        1. Берём подтверждённые документы за квартал с vat_amount > 0.
        2. Типы: INVOICE, UPD, TORG12, ACT.
        3. Создаём по одной записи на каждый документ.
        """
        user_id_str = str(user_id)
        start_date, end_date = _quarter_date_range(year, quarter)

        # Удаляем старые записи при overwrite
        if overwrite:
            await self.db.execute(
                delete(PurchaseBookEntry).where(
                    and_(
                        PurchaseBookEntry.user_id == user_id_str,
                        PurchaseBookEntry.year == year,
                        PurchaseBookEntry.quarter == quarter,
                    )
                )
            )
        else:
            # Проверяем, есть ли уже записи
            existing = await self.db.execute(
                select(func.count(PurchaseBookEntry.id)).where(
                    and_(
                        PurchaseBookEntry.user_id == user_id_str,
                        PurchaseBookEntry.year == year,
                        PurchaseBookEntry.quarter == quarter,
                    )
                )
            )
            if existing.scalar_one() > 0:
                totals = await self.get_totals(user_id, year, quarter)
                return {
                    "created_entries": 0,
                    **totals,
                    "year": year,
                    "quarter": quarter,
                }

        # Выбираем подтверждённые документы за квартал с НДС
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.counterparty))
            .where(
                and_(
                    Document.user_id == user_id_str,
                    Document.status == DocumentStatus.CONFIRMED,
                    Document.doc_type.in_(_PURCHASE_DOC_TYPES),
                    Document.doc_date >= start_date,
                    Document.doc_date <= end_date,
                    Document.vat_amount.isnot(None),
                    Document.vat_amount > Decimal("0"),
                )
            )
            .order_by(Document.doc_date, Document.created_at)
        )
        documents = result.scalars().all()

        total_without_vat = Decimal("0.00")
        total_vat = Decimal("0.00")
        total_with_vat = Decimal("0.00")
        entry_number = 1

        for doc in documents:
            doc_without_vat = doc.total_without_vat or Decimal("0.00")
            doc_vat = doc.vat_amount or Decimal("0.00")
            doc_with_vat = doc.total_with_vat or (doc_without_vat + doc_vat)
            doc_vat_rate = doc.vat_rate or Decimal("20.00")

            # Данные контрагента — только ID, остальные данные берутся через relationship
            cp_id: str | None = doc.counterparty_id

            entry = PurchaseBookEntry(
                user_id=user_id_str,
                entry_number=entry_number,
                entry_date=doc.doc_date,
                counterparty_id=cp_id,
                invoice_number=doc.doc_number,
                invoice_date=doc.doc_date,
                total_without_vat=doc_without_vat,
                vat_amount=doc_vat,
                total_with_vat=doc_with_vat,
                vat_rate=doc_vat_rate,
                quarter=quarter,
                year=year,
                linked_document_id=str(doc.id),
            )
            self.db.add(entry)

            total_without_vat += doc_without_vat
            total_vat += doc_vat
            total_with_vat += doc_with_vat
            entry_number += 1

        await self.db.flush()

        return {
            "created_entries": entry_number - 1,
            "total_without_vat": total_without_vat,
            "total_vat": total_vat,
            "total_with_vat": total_with_vat,
            "year": year,
            "quarter": quarter,
        }