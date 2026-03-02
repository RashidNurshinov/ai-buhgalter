"""
API роутер для банковских операций.
Пункт плана: 1.10.8

Эндпоинты:
- GET  /api/v1/operations/              — список операций с фильтрами
- GET  /api/v1/operations/{id}          — детали операции
- POST /api/v1/operations/{id}/confirm  — подтвердить классификацию
- POST /api/v1/operations/{id}/reclassify — ручная переклассификация
- GET  /api/v1/operations/unconfirmed   — операции, ожидающие подтверждения
- POST /api/v1/operations/{id}/classify — классифицировать одну операцию через ИИ
- POST /api/v1/operations/classify-batch — пакетная классификация
"""

import math
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import OperationCategory, OperationStatus
from app.core.dependencies import get_current_user, get_db
from app.models.bank_operation import BankOperation
from app.models.user import User
from app.schemas.bank_operation import (
    BankOperationResponse,
    OperationConfirmRequest,
    OperationReclassifyRequest,
)
from app.schemas.common import PaginatedResponse
from app.services.classifier_service import (
    apply_classification,
    apply_match_result,
    classify_bank_operation,
    classify_operations_batch,
    detect_duplicate_operations,
    match_operation_with_document,
    match_operation_with_receipt,
    ClassificationResult,
)

router = APIRouter(prefix="/operations", tags=["operations"])


# ─── GET /operations/ — список операций ──────────────────────────


@router.get("/", response_model=PaginatedResponse)
async def list_operations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(20, ge=1, le=100, description="Элементов на странице"),
    date_from: date | None = Query(None, description="Дата от"),
    date_to: date | None = Query(None, description="Дата до"),
    category: OperationCategory | None = Query(None, description="Категория"),
    operation_status: OperationStatus | None = Query(None, alias="status", description="Статус"),
    is_income: bool | None = Query(None, description="Только доходы"),
    is_expense: bool | None = Query(None, description="Только расходы"),
    search: str | None = Query(None, description="Поиск по назначению платежа"),
):
    """Список банковских операций текущего пользователя с фильтрами и пагинацией."""
    # Базовый запрос
    query = select(BankOperation).where(BankOperation.user_id == current_user.id)
    count_query = select(func.count(BankOperation.id)).where(
        BankOperation.user_id == current_user.id
    )

    # Фильтры
    if date_from:
        query = query.where(BankOperation.operation_date >= date_from)
        count_query = count_query.where(BankOperation.operation_date >= date_from)
    if date_to:
        query = query.where(BankOperation.operation_date <= date_to)
        count_query = count_query.where(BankOperation.operation_date <= date_to)
    if category:
        query = query.where(BankOperation.category == category)
        count_query = count_query.where(BankOperation.category == category)
    if operation_status:
        query = query.where(BankOperation.status == operation_status)
        count_query = count_query.where(BankOperation.status == operation_status)
    if is_income is not None:
        query = query.where(BankOperation.is_income == is_income)
        count_query = count_query.where(BankOperation.is_income == is_income)
    if is_expense is not None:
        query = query.where(BankOperation.is_expense == is_expense)
        count_query = count_query.where(BankOperation.is_expense == is_expense)
    if search:
        search_filter = BankOperation.purpose.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Общее количество
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Сортировка и пагинация
    offset = (page - 1) * per_page
    query = query.order_by(desc(BankOperation.operation_date), desc(BankOperation.created_at))
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    operations = list(result.scalars().all())

    return PaginatedResponse(
        items=[BankOperationResponse.model_validate(op) for op in operations],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if per_page > 0 else 0,
    )


# ─── GET /operations/unconfirmed — ожидающие подтверждения ───────


@router.get("/unconfirmed", response_model=PaginatedResponse)
async def list_unconfirmed_operations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Операции, ожидающие подтверждения классификации (status=pending или classified с низкой уверенностью)."""
    query = select(BankOperation).where(
        BankOperation.user_id == current_user.id,
        BankOperation.status.in_([OperationStatus.PENDING, OperationStatus.CLASSIFIED]),
    )
    count_query = select(func.count(BankOperation.id)).where(
        BankOperation.user_id == current_user.id,
        BankOperation.status.in_([OperationStatus.PENDING, OperationStatus.CLASSIFIED]),
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * per_page
    query = query.order_by(
        BankOperation.classification_confidence.asc().nullsfirst(),
        desc(BankOperation.operation_date),
    ).offset(offset).limit(per_page)

    result = await db.execute(query)
    operations = list(result.scalars().all())

    return PaginatedResponse(
        items=[BankOperationResponse.model_validate(op) for op in operations],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if per_page > 0 else 0,
    )


# ─── GET /operations/{id} — детали операции ──────────────────────


@router.get("/{operation_id}", response_model=BankOperationResponse)
async def get_operation(
    operation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить детали одной операции."""
    result = await db.execute(
        select(BankOperation).where(
            BankOperation.id == operation_id,
            BankOperation.user_id == current_user.id,
        )
    )
    operation = result.scalar_one_or_none()
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Операция не найдена",
        )
    return BankOperationResponse.model_validate(operation)


# ─── POST /operations/{id}/confirm — подтвердить классификацию ───


@router.post("/{operation_id}/confirm", response_model=BankOperationResponse)
async def confirm_operation(
    operation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Подтвердить классификацию операции пользователем."""
    result = await db.execute(
        select(BankOperation).where(
            BankOperation.id == operation_id,
            BankOperation.user_id == current_user.id,
        )
    )
    operation = result.scalar_one_or_none()
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Операция не найдена",
        )

    operation.status = OperationStatus.CONFIRMED
    await db.commit()
    await db.refresh(operation)

    return BankOperationResponse.model_validate(operation)


# ─── POST /operations/{id}/reclassify — переклассификация ────────


@router.post("/{operation_id}/reclassify", response_model=BankOperationResponse)
async def reclassify_operation(
    operation_id: str,
    body: OperationReclassifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ручная переклассификация операции пользователем."""
    result = await db.execute(
        select(BankOperation).where(
            BankOperation.id == operation_id,
            BankOperation.user_id == current_user.id,
        )
    )
    operation = result.scalar_one_or_none()
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Операция не найдена",
        )

    operation.category = body.category

    # Автоматически определяем is_income / is_expense по категории
    from app.services.classifier_service import INCOME_CATEGORIES, EXPENSE_CATEGORIES

    if body.is_income is not None:
        operation.is_income = body.is_income
    else:
        operation.is_income = body.category in INCOME_CATEGORIES

    if body.is_expense is not None:
        operation.is_expense = body.is_expense
    else:
        operation.is_expense = body.category in EXPENSE_CATEGORIES

    # Для категорий «не доход и не расход» — оба False
    neutral_categories = {
        OperationCategory.OWN_FUNDS,
        OperationCategory.INTERNAL_TRANSFER,
        OperationCategory.LOAN_RECEIVED,
        OperationCategory.PERSONAL_WITHDRAWAL,
        OperationCategory.CASH_WITHDRAWAL,
    }
    if body.category in neutral_categories:
        operation.is_income = False
        operation.is_expense = False

    if body.vat_amount is not None:
        operation.vat_amount = body.vat_amount

    if body.linked_document_id is not None:
        operation.linked_document_id = str(body.linked_document_id)

    operation.status = OperationStatus.RECLASSIFIED
    operation.classification_confidence = Decimal("1.0000")  # Ручная классификация = 100%

    await db.commit()
    await db.refresh(operation)

    return BankOperationResponse.model_validate(operation)


# ─── POST /operations/{id}/classify — классифицировать через ИИ ──


@router.post("/{operation_id}/classify", response_model=dict)
async def classify_single_operation(
    operation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запустить ИИ-классификацию для одной операции."""
    result = await db.execute(
        select(BankOperation).where(
            BankOperation.id == operation_id,
            BankOperation.user_id == current_user.id,
        )
    )
    operation = result.scalar_one_or_none()
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Операция не найдена",
        )

    # Классификация
    classification = await classify_bank_operation(db, operation)

    # Применяем результат
    await apply_classification(db, operation.id, current_user.id, classification)

    # Пробуем сопоставить с документом
    doc_match = await match_operation_with_document(db, operation)
    if doc_match.matched:
        await apply_match_result(db, operation.id, current_user.id, doc_match)

    # Пробуем сопоставить с чеком ОФД (если это входящая операция)
    receipt_match = None
    if operation.is_income:
        receipt_match = await match_operation_with_receipt(db, operation)
        if receipt_match.matched:
            await apply_match_result(db, operation.id, current_user.id, receipt_match)

    await db.commit()

    return {
        "operation_id": operation.id,
        "classification": {
            "category": classification.category.value,
            "is_income": classification.is_income,
            "is_expense": classification.is_expense,
            "vat_amount": str(classification.vat_amount) if classification.vat_amount is not None else None,
            "confidence": classification.confidence,
            "reasoning": classification.reasoning,
            "source": classification.source,
        },
        "document_match": {
            "matched": doc_match.matched,
            "entity_id": doc_match.entity_id if doc_match.matched else None,
            "score": doc_match.match_score,
            "reason": doc_match.match_reason,
        } if doc_match else None,
        "receipt_match": {
            "matched": receipt_match.matched,
            "entity_id": receipt_match.entity_id if receipt_match.matched else None,
            "score": receipt_match.match_score,
            "reason": receipt_match.match_reason,
        } if receipt_match else None,
    }


# ─── POST /operations/classify-batch — пакетная классификация ────


@router.post("/classify-batch", response_model=dict)
async def classify_batch(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: OperationStatus = Query(
        OperationStatus.PENDING,
        alias="status",
        description="Статус операций для классификации",
    ),
    limit: int = Query(50, ge=1, le=200, description="Макс. количество операций"),
):
    """
    Пакетная ИИ-классификация неклассифицированных операций.
    По умолчанию классифицирует до 50 операций со статусом PENDING.
    """
    # Получаем операции
    result = await db.execute(
        select(BankOperation).where(
            BankOperation.user_id == current_user.id,
            BankOperation.status == status_filter,
        ).order_by(BankOperation.operation_date).limit(limit)
    )
    operations = list(result.scalars().all())

    if not operations:
        return {
            "total_processed": 0,
            "classified": 0,
            "pending_confirmation": 0,
            "errors": 0,
            "message": "Нет операций для классификации",
        }

    # Пакетная классификация
    classifications = await classify_operations_batch(db, operations)

    classified_count = 0
    pending_count = 0
    error_count = 0

    # Применяем результаты
    for op, cls_result in zip(operations, classifications):
        try:
            await apply_classification(db, op.id, current_user.id, cls_result)
            if cls_result.confidence >= 0.9:
                classified_count += 1
            else:
                pending_count += 1
        except Exception:
            error_count += 1

    await db.commit()

    return {
        "total_processed": len(operations),
        "classified": classified_count,
        "pending_confirmation": pending_count,
        "errors": error_count,
        "message": f"Обработано {len(operations)} операций",
    }


# ─── POST /operations/detect-duplicates — поиск дублей ───────────


@router.post("/detect-duplicates", response_model=dict)
async def detect_duplicates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
):
    """Поиск потенциальных дублей операций за период."""
    duplicates = await detect_duplicate_operations(
        db, current_user.id, date_from, date_to
    )

    return {
        "total_groups": len(duplicates),
        "duplicates": [
            {
                "operation_ids": group.operation_ids,
                "reason": group.reason,
                "amount": str(group.total_amount),
                "date": str(group.date) if group.date else None,
            }
            for group in duplicates
        ],
    }