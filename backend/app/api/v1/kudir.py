"""
API эндпоинты КУДиР (Книга учёта доходов и расходов).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → api/v1/kudir.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.kudir import (
    KudirGenerateRequest,
    KudirPeriodResponse,
)
from app.services.kudir_service import KudirService
from app.services.export_service import export_kudir_excel, export_kudir_pdf

router = APIRouter(prefix="/kudir", tags=["КУДиР"])


@router.get(
    "",
    response_model=KudirPeriodResponse,
    summary="Получить записи КУДиР за период",
)
async def get_kudir(
    year: int = Query(..., ge=2020, le=2030, description="Год"),
    quarter: int | None = Query(None, ge=1, le=4, description="Квартал (опц.)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получить все записи КУДиР за указанный год и опционально квартал.
    Возвращает список записей и итоговые суммы.
    """
    service = KudirService(db)
    entries = await service.get_entries(current_user.id, year, quarter)
    totals = await service.get_totals(current_user.id, year, quarter)

    return KudirPeriodResponse(
        entries=entries,
        total_income=totals["total_income"],
        total_expense=totals["total_expense"],
        net_result=totals["net_result"],
        quarter=quarter,
        year=year,
    )


@router.post(
    "/generate",
    response_model=KudirPeriodResponse,
    summary="Сгенерировать ��аписи КУДиР",
)
async def generate_kudir(
    data: KudirGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Сгенерировать записи КУДиР на основе подтверждённых банковских операций.

    - **year** — год
    - **quarter** — квартал (опционально; если не указан — весь год)
    - **overwrite** — перезаписать существующие записи
    """
    service = KudirService(db)
    try:
        result = await service.generate(
            user_id=current_user.id,
            year=data.year,
            quarter=data.quarter,
            overwrite=data.overwrite,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации КУДиР: {str(e)}",
        )

    # Коммитим транзакцию
    await db.commit()

    # Возвращаем актуальные данные
    entries = await service.get_entries(current_user.id, data.year, data.quarter)
    totals = await service.get_totals(current_user.id, data.year, data.quarter)

    return KudirPeriodResponse(
        entries=entries,
        total_income=totals["total_income"],
        total_expense=totals["total_expense"],
        net_result=totals["net_result"],
        quarter=data.quarter,
        year=data.year,
    )


@router.get(
    "/export/excel",
    summary="Экспорт КУДиР в Excel",
    responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}},
)
async def export_kudir_to_excel(
    year: int = Query(..., ge=2020, le=2030, description="Год"),
    quarter: int | None = Query(None, ge=1, le=4, description="Квартал (опц.)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт КУДиР в формат Excel (XLSX)."""
    service = KudirService(db)
    entries = await service.get_entries(current_user.id, year, quarter)
    totals = await service.get_totals(current_user.id, year, quarter)

    excel_bytes = export_kudir_excel(
        entries=entries,
        totals=totals,
        year=year,
        quarter=quarter,
        user_name=current_user.full_name or "",
        inn=current_user.inn or "",
    )

    q_suffix = f"_Q{quarter}" if quarter else ""
    filename = f"KUDiR_{year}{q_suffix}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/export/pdf",
    summary="Экспорт КУДиР в PDF",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def export_kudir_to_pdf(
    year: int = Query(..., ge=2020, le=2030, description="Год"),
    quarter: int | None = Query(None, ge=1, le=4, description="Квартал (опц.)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт КУДиР в формат PDF."""
    service = KudirService(db)
    entries = await service.get_entries(current_user.id, year, quarter)
    totals = await service.get_totals(current_user.id, year, quarter)

    pdf_bytes = export_kudir_pdf(
        entries=entries,
        totals=totals,
        year=year,
        quarter=quarter,
        user_name=current_user.full_name or "",
        inn=current_user.inn or "",
    )

    q_suffix = f"_Q{quarter}" if quarter else ""
    filename = f"KUDiR_{year}{q_suffix}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )