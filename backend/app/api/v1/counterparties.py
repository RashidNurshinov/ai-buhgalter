"""
CRUD API для контрагентов.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.counterparty import Counterparty
from app.models.user import User
from app.schemas.counterparty import (
    CounterpartyCreate,
    CounterpartyResponse,
    CounterpartyUpdate,
)

router = APIRouter(prefix="/counterparties", tags=["counterparties"])


@router.get("/", response_model=list[CounterpartyResponse])
async def list_counterparties(
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список контрагентов текущего пользователя."""
    query = select(Counterparty).where(Counterparty.user_id == current_user.id)
    if search:
        query = query.where(
            Counterparty.name.ilike(f"%{search}%")
            | Counterparty.inn.ilike(f"%{search}%")
        )
    query = query.order_by(Counterparty.name).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=CounterpartyResponse, status_code=status.HTTP_201_CREATED)
async def create_counterparty(
    data: CounterpartyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать контрагента."""
    counterparty = Counterparty(
        user_id=current_user.id,
        name=data.name,
        inn=data.inn,
        kpp=data.kpp,
        address=data.address,
    )
    db.add(counterparty)
    await db.flush()
    await db.refresh(counterparty)
    return counterparty


@router.get("/{counterparty_id}", response_model=CounterpartyResponse)
async def get_counterparty(
    counterparty_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить контрагента по ID."""
    result = await db.execute(
        select(Counterparty).where(
            Counterparty.id == counterparty_id,
            Counterparty.user_id == current_user.id,
        )
    )
    counterparty = result.scalar_one_or_none()
    if not counterparty:
        raise HTTPException(status_code=404, detail="Контрагент не найден")
    return counterparty


@router.put("/{counterparty_id}", response_model=CounterpartyResponse)
async def update_counterparty(
    counterparty_id: uuid.UUID,
    data: CounterpartyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить контрагента."""
    result = await db.execute(
        select(Counterparty).where(
            Counterparty.id == counterparty_id,
            Counterparty.user_id == current_user.id,
        )
    )
    counterparty = result.scalar_one_or_none()
    if not counterparty:
        raise HTTPException(status_code=404, detail="Контрагент не найден")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(counterparty, field, value)

    await db.flush()
    await db.refresh(counterparty)
    return counterparty


@router.delete("/{counterparty_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_counterparty(
    counterparty_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить контрагента."""
    result = await db.execute(
        select(Counterparty).where(
            Counterparty.id == counterparty_id,
            Counterparty.user_id == current_user.id,
        )
    )
    counterparty = result.scalar_one_or_none()
    if not counterparty:
        raise HTTPException(status_code=404, detail="Контрагент не найден")
    await db.delete(counterparty)
    await db.flush()
