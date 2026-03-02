"""
Сервис генерации и получения записей книги продаж.
Генерирует записи на основе исходящих документов и кассовых чеков с НДС.

Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → services/sales_book_service.py
"""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.enums import DocumentStatus, DocumentType
from app.models.book_entry import SalesBookEntry
from app.models.cash_receipt import CashReceipt
from app.models.document import Document


# Типы исходящих документов для книги продаж
_SALES_DOC_TYPES = (
    DocumentType.INVOICE,
    DocumentType.UPD,
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


class SalesBookService:
    """Сервис для работы с книгой продаж."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Получение записей ──────────────────────────

    async def get_entries(
        self,
        user_id: uuid.UUID,
        year: int,
        quarter: int,
    ) -> list[SalesBookEntry]:
        """Получить записи книги продаж за квартал."""
        result = await self.db.execute(
            select(SalesBookEntry)
            .where(
                and_(
                    SalesBookEntry.user_id == str(user_id),
                    SalesBookEntry.year == year,
                    SalesBookEntry.quarter == quarter,
                )
            )
            .order_by(SalesBookEntry.entry_number)
        )
        return list(result.scalars().all())

    async def get_totals(
        self,
        user_id: uuid.UUID,
        year: int,
        quarter: int,
    ) -> dict:
        """Посчитать итоги книги продаж за квартал."""
        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(SalesBookEntry.total_without_vat), Decimal("0.00")
                ).label("total_without_vat"),
                func.coalesce(
                    func.sum(SalesBookEntry.vat_amount), Decimal("0.00")
                ).label("total_vat"),
                func.coalesce(
                    func.sum(SalesBookEntry.total_with_vat), Decimal("0.00")
                ).label("total_with_vat"),
            ).where(
                and_(
                    SalesBookEntry.user_id == str(user_id),
                    SalesBookEntry.year == year,
                    SalesBookEntry.quarter == quarter,
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
        Сгенерировать записи книги продаж на основе:
        1. Подтверждённых исходящих документов (INVOICE, UPD) с НДС.
        2. Кассовых чеков с НДС за квартал.
        """
        user_id_str = str(user_id)
        start_date, end_date = _quarter_date_range(year, quarter)

        # Удаляем старые записи при overwrite
        if overwrite:
            await self.db.execute(
                delete(SalesBookEntry).where(
                    and_(
                        SalesBookEntry.user_id == user_id_str,
                        SalesBookEntry.year == year,
                        SalesBookEntry.quarter == quarter,
                    )
                )
            )
        else:
            # Проверяем, есть ли уже записи
            existing = await self.db.execute(
                select(func.count(SalesBookEntry.id)).where(
                    and_(
                        SalesBookEntry.user_id == user_id_str,
                        SalesBookEntry.year == year,
                        SalesBookEntry.quarter == quarter,
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

        total_without_vat = Decimal("0.00")
        total_vat = Decimal("0.00")
        total_with_vat = Decimal("0.00")
        entry_number = 1

        # ── 1. Исходящие документы ──────────────────
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.counterparty))
            .where(
                and_(
                    Document.user_id == user_id_str,
                    Document.status == DocumentStatus.CONFIRMED,
                    Document.doc_type.in_(_SALES_DOC_TYPES),
                    Document.doc_date >= start_date,
                    Document.doc_date <= end_date,
                    Document.vat_amount.isnot(None),
                    Document.vat_amount > Decimal("0"),
                )
            )
            .order_by(Document.doc_date, Document.created_at)
        )
        documents = result.scalars().all()

        for doc in documents:
            doc_without_vat = doc.total_without_vat or Decimal("0.00")
            doc_vat = doc.vat_amount or Decimal("0.00")
            doc_with_vat = doc.total_with_vat or (doc_without_vat + doc_vat)
            doc_vat_rate = doc.vat_rate or Decimal("20.00")

            # Данные покупателя (из контрагента документа)
            buyer_name: str | None = None
            buyer_inn: str | None = None
            buyer_kpp: str | None = None

            if doc.counterparty:
                buyer_name = getattr(doc.counterparty, "name", None)
                buyer_inn = getattr(doc.counterparty, "inn", None)
                buyer_kpp = getattr(doc.counterparty, "kpp", None)

            entry = SalesBookEntry(
                user_id=user_id_str,
                entry_number=entry_number,
                entry_date=doc.doc_date,
                buyer_name=buyer_name,
                buyer_inn=buyer_inn,
                buyer_kpp=buyer_kpp,
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

        # ── 2. Кассовые чеки ───────────────────────
        start_dt = datetime.datetime.combine(
            start_date, datetime.time.min, tzinfo=datetime.timezone.utc
        )
        end_dt = datetime.datetime.combine(
            end_date, datetime.time.max, tzinfo=datetime.timezone.utc
        )

        result = await self.db.execute(
            select(CashReceipt)
            .where(
                and_(
                    CashReceipt.user_id == user_id_str,
                    CashReceipt.receipt_date >= start_dt,
                    CashReceipt.receipt_date <= end_dt,
                    CashReceipt.vat_amount.isnot(None),
                    CashReceipt.vat_amount > Decimal("0"),
                )
            )
            .order_by(CashReceipt.receipt_date)
        )
        receipts = result.scalars().all()

        for receipt in receipts:
            receipt_vat = receipt.vat_amount or Decimal("0.00")
            receipt_total = receipt.total
            receipt_without_vat = receipt_total - receipt_vat

            # Определяем ставку НДС по соотношению
            if receipt_without_vat > Decimal("0"):
                vat_rate = (
                    receipt_vat / receipt_without_vat * Decimal("100")
                ).quantize(Decimal("0.01"))
            else:
                vat_rate = Decimal("20.00")

            entry = SalesBookEntry(
                user_id=user_id_str,
                entry_number=entry_number,
                entry_date=receipt.receipt_date.date()
                if hasattr(receipt.receipt_date, "date")
                else receipt.receipt_date,
                buyer_name="Розничный покупатель",
                buyer_inn=None,
                buyer_kpp=None,
                invoice_number=receipt.receipt_number or receipt.fiscal_number,
                invoice_date=receipt.receipt_date.date()
                if hasattr(receipt.receipt_date, "date")
                else receipt.receipt_date,
                total_without_vat=receipt_without_vat,
                vat_amount=receipt_vat,
                total_with_vat=receipt_total,
                vat_rate=vat_rate,
                quarter=quarter,
                year=year,
                linked_receipt_id=str(receipt.id),
            )
            self.db.add(entry)

            total_without_vat += receipt_without_vat
            total_vat += receipt_vat
            total_with_vat += receipt_total
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