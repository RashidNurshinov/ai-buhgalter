"""
Роутер для управления документами.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → api/v1/documents.py

Эндпоинты:
- GET  /api/v1/documents/          — список документов
- GET  /api/v1/documents/{id}      — ��етали документа
- POST /api/v1/documents/{id}/confirm  — подтвердить документ
- POST /api/v1/documents/{id}/reject   — отклонить документ
- PATCH /api/v1/documents/{id}     — редактировать документ
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.enums import DocumentStatus, DocumentType
from app.core.dependencies import get_current_user, get_db
from app.models.document import Document, DocumentItem
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.document import (
    DocumentConfirmRequest,
    DocumentResponse,
    DocumentUpdate,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=PaginatedResponse)
async def list_documents(
    doc_type: DocumentType | None = Query(None, description="Фильтр по типу"),
    status_filter: DocumentStatus | None = Query(None, alias="status", description="Фильтр по статусу"),
    year: int | None = Query(None, ge=2020, le=2030),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список документов пользователя с фильтрацией и пагинацией."""
    query = select(Document).where(Document.user_id == current_user.id)

    if doc_type is not None:
        query = query.where(Document.doc_type == doc_type)
    if status_filter is not None:
        query = query.where(Document.status == status_filter)
    if year is not None:
        query = query.where(func.extract("year", Document.doc_date) == year)

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Fetch with pagination
    query = query.options(selectinload(Document.items))
    query = query.order_by(desc(Document.created_at))
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    documents = list(result.scalars().all())

    return PaginatedResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Детали документа."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id, Document.user_id == current_user.id)
        .options(selectinload(Document.items))
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return DocumentResponse.model_validate(document)


@router.post("/{document_id}/confirm", response_model=DocumentResponse)
async def confirm_document(
    document_id: uuid.UUID,
    body: DocumentConfirmRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Подтвердить распознанный документ (с возможными правками)."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id, Document.user_id == current_user.id)
        .options(selectinload(Document.items))
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Документ не найден")

    if document.status not in (DocumentStatus.RECOGNIZED, DocumentStatus.PROCESSING):
        raise HTTPException(
            status_code=400,
            detail=f"Невозможно подтвердить документ в статусе '{document.status.value}'",
        )

    # Применяем корректировки если переданы
    if body and body.corrections:
        corrections = body.corrections
        if corrections.doc_type is not None:
            document.doc_type = corrections.doc_type
        if corrections.doc_number is not None:
            document.doc_number = corrections.doc_number
        if corrections.doc_date is not None:
            document.doc_date = corrections.doc_date
        if corrections.total_without_vat is not None:
            document.total_without_vat = corrections.total_without_vat
        if corrections.vat_amount is not None:
            document.vat_amount = corrections.vat_amount
        if corrections.total_with_vat is not None:
            document.total_with_vat = corrections.total_with_vat
        if corrections.vat_rate is not None:
            document.vat_rate = corrections.vat_rate

    document.status = DocumentStatus.CONFIRMED
    await db.flush()

    return DocumentResponse.model_validate(document)


@router.post("/{document_id}/reject", response_model=DocumentResponse)
async def reject_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Отклонить документ."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id, Document.user_id == current_user.id)
        .options(selectinload(Document.items))
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Документ не найден")

    document.status = DocumentStatus.REJECTED
    await db.flush()

    return DocumentResponse.model_validate(document)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Редактирование документа."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id, Document.user_id == current_user.id)
        .options(selectinload(Document.items))
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Документ не найден")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(document, field, value)

    await db.flush()

    return DocumentResponse.model_validate(document)