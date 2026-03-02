"""
API эндпоинты книги продаж.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → api/v1/sales_book.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.sales_book import (
    SalesBookGenerateRequest,
    SalesBookPeriodResponse,
)
from app.services.sales_book_service import SalesBookService
from app.services.export_service import export_sales_book_excel

router = APIRouter(prefix="/sales-book", tags=["Книга продаж"])


@router.get(
    "",
    response_model=SalesBookPeriodResponse,
    summary="Получить записи книги продаж за квартал",
)
async def get_sales_book(
    year: int = Query(..., ge=2020, le=2030, description="Год"),
    quarter: int = Query(..., ge=1, le=4, description="Квартал"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получить все записи книги продаж за указанный квартал.
    Возвращает список записей и итоговые суммы.
    """
    service = SalesBookService(db)
    entries = await service.get_entries(current_user.id, year, quarter)
    totals = await service.get_totals(current_user.id, year, quarter)

    return SalesBookPeriodResponse(
        entries=entries,
        total_without_vat=totals["total_without_vat"],
        total_vat=totals["total_vat"],
        total_with_vat=totals["total_with_vat"],
        quarter=quarter,
        year=year,
    )


@router.post(
    "/generate",
    response_model=SalesBookPeriodResponse,
    summary="Сгенерировать записи книги продаж",
)
async def generate_sales_book(
    data: SalesBookGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Сгенерировать записи книги продаж на основе:
    - подтверждённых исходящих документов (счёт-фактура, УПД) с НДС
    - кассовых чеков с НДС
    """
    service = SalesBookService(db)
    try:
        await service.generate(
            user_id=current_user.id,
            year=data.year,
            quarter=data.quarter,
            overwrite=data.overwrite,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации книги продаж: {str(e)}",
        )

    await db.commit()

    entries = await service.get_entries(current_user.id, data.year, data.quarter)
    totals = await service.get_totals(current_user.id, data.year, data.quarter)

    return SalesBookPeriodResponse(
        entries=entries,
        total_without_vat=totals["total_without_vat"],
        total_vat=totals["total_vat"],
        total_with_vat=totals["total_with_vat"],
        quarter=data.quarter,
        year=data.year,
    )


@router.get(
    "/export/excel",
    summary="Экспорт книги продаж в Excel",
    responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}},
)
async def export_sales_book_to_excel(
    year: int = Query(..., ge=2020, le=2030, description="Год"),
    quarter: int = Query(..., ge=1, le=4, description="Квартал"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт книги продаж в формат Excel (XLSX)."""
    service = SalesBookService(db)
    entries = await service.get_entries(current_user.id, year, quarter)
    totals = await service.get_totals(current_user.id, year, quarter)

    excel_bytes = export_sales_book_excel(
        entries=entries,
        totals=totals,
        year=year,
        quarter=quarter,
        user_name=current_user.full_name or "",
        inn=current_user.inn or "",
    )

    filename = f"Sales_Book_{year}_Q{quarter}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )