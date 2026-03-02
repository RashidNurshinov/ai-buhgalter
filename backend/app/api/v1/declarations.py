"""
API роутер: налоговые декларации.
Пункт плана: 1.13.4

Эндпоинты:
- POST /api/v1/declarations/generate       — сформировать декларацию
- GET  /api/v1/declarations/               — список деклараций
- GET  /api/v1/declarations/{id}           — получить декларацию по ID
- GET  /api/v1/declarations/{id}/xml       — получить XML декларации
- POST /api/v1/declarations/{id}/validate  — валидировать декларацию
- GET  /api/v1/declarations/{id}/download/pdf — PDF-предпросмотр
"""

import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import DeclarationType
from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.declaration import (
    ControlRatioErrorResponse,
    DeclarationGenerateRequest,
    DeclarationGenerateResponse,
    DeclarationResponse,
    DeclarationValidateResponse,
    DeclarationXmlResponse,
)
from app.services.declaration_generator_service import DeclarationGeneratorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/declarations", tags=["declarations"])


# ─── POST /declarations/generate — сформировать декларацию ─────


@router.post(
    "/generate",
    response_model=DeclarationGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Сформировать налоговую декларацию",
    description=(
        "Генерирует XML декларации на основе расчётов налогов. "
        "Автоматически проводит XSD-валидацию и проверку контрольных соотношений ФНС."
    ),
)
async def generate_declaration(
    request: DeclarationGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeclarationGenerateResponse:
    """Сформировать налоговую декларацию."""
    if request.declaration_type == DeclarationType.VAT and request.quarter is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Для декларации НДС необходимо указать квартал (quarter).",
        )

    service = DeclarationGeneratorService(db, current_user)

    try:
        result = await service.generate(
            declaration_type=request.declaration_type,
            year=request.year,
            quarter=request.quarter,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    await db.commit()

    return DeclarationGenerateResponse(
        declaration_id=result.declaration_id,
        declaration_type=result.declaration_type,
        period=result.period,
        year=result.year,
        status=result.status,
        xsd_valid=result.xsd_valid,
        xsd_errors=result.xsd_errors,
        control_ratios_valid=result.control_ratios_valid,
        control_ratios_errors=[
            ControlRatioErrorResponse(**e) for e in result.control_ratios_errors
        ],
        warnings=result.warnings,
    )


# ─── GET /declarations/ — список деклараций ────────────────────


@router.get(
    "/",
    response_model=list[DeclarationResponse],
    summary="Список деклараций",
    description="Получить список сформированных деклараций с фильтрацией.",
)
async def list_declarations(
    year: int | None = Query(None, ge=2020, le=2030, description="Фильтр по году"),
    declaration_type: DeclarationType | None = Query(
        None, description="Фильтр по типу декларации"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DeclarationResponse]:
    """Получить список деклараций."""
    service = DeclarationGeneratorService(db, current_user)
    declarations = await service.get_list(
        year=year,
        declaration_type=declaration_type,
        skip=skip,
        limit=limit,
    )
    return [DeclarationResponse.model_validate(d) for d in declarations]


# ─── GET /declarations/{id} — декларация по ID ────────────────


@router.get(
    "/{declaration_id}",
    response_model=DeclarationResponse,
    summary="Получить декларацию по ID",
)
async def get_declaration(
    declaration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeclarationResponse:
    """Получить декларацию по ID."""
    service = DeclarationGeneratorService(db, current_user)
    declaration = await service.get_by_id(declaration_id)

    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Декларация {declaration_id} не найдена",
        )

    return DeclarationResponse.model_validate(declaration)


# ─── GET /declarations/{id}/xml — XML декларации ──────────────


@router.get(
    "/{declaration_id}/xml",
    response_model=DeclarationXmlResponse,
    summary="Получить XML декларации",
    description="Возвращает XML-содержимое декларации для скачивания или просмотра.",
)
async def get_declaration_xml(
    declaration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeclarationXmlResponse:
    """Получить XML-содержимое декларации."""
    service = DeclarationGeneratorService(db, current_user)
    declaration = await service.get_by_id(declaration_id)

    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Декларация {declaration_id} не найдена",
        )

    if not declaration.xml_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="XML-содержимое декларации отсутствует",
        )

    return DeclarationXmlResponse.model_validate(declaration)


# ─── POST /declarations/{id}/validate — валидация ─────────────


@router.post(
    "/{declaration_id}/validate",
    response_model=DeclarationValidateResponse,
    summary="Валидировать декларацию",
    description=(
        "Проверить декларацию: XSD-валидация XML и проверка "
        "контрольных соотношений ФНС. Обновляет статус декларации."
    ),
)
async def validate_declaration(
    declaration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeclarationValidateResponse:
    """Валидировать декларацию."""
    service = DeclarationGeneratorService(db, current_user)

    try:
        result = await service.validate(declaration_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    await db.commit()

    return DeclarationValidateResponse(
        declaration_id=result["declaration_id"],
        status=result["status"],
        xsd_valid=result["xsd_valid"],
        xsd_errors=result["xsd_errors"],
        control_ratios_valid=result["control_ratios_valid"],
        control_ratios_errors=[
            ControlRatioErrorResponse(**e)
            for e in result["control_ratios_errors"]
        ],
    )


# ─── GET /declarations/{id}/download/pdf — PDF-предпросмотр ───


@router.get(
    "/{declaration_id}/download/pdf",
    summary="Скачать PDF-предпросмотр декларации",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_declaration_pdf(
    declaration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Генерирует PDF-предпросмотр декларации в «человеческом» виде."""
    from app.services.export_service import export_declaration_pdf_preview

    service = DeclarationGeneratorService(db, current_user)
    declaration = await service.get_by_id(declaration_id)

    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Декларация {declaration_id} не найдена",
        )

    if not declaration.xml_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="XML-содержимое декларации отсутствует",
        )

    pdf_bytes = export_declaration_pdf_preview(
        xml_content=declaration.xml_content,
        declaration_type=declaration.declaration_type.value,
        period=declaration.period,
        year=declaration.year,
        user_name=current_user.full_name or "",
        inn=current_user.inn or "",
    )

    filename = f"Declaration_{declaration.declaration_type.value}_{declaration.period}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )