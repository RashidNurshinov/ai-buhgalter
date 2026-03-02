"""
API эндпоинты профиля пользователя и настроек.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → api/v1/users.py

Настройки объединены в таблицу users (без отдельной user_settings).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Пользователи"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Получить профиль текущего пользователя",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Получить полный профиль текущего пользователя с настройками."""
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Обновить профиль текущего пользователя",
)
async def update_my_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить данные профиля и настройки.
    Передаются только изменяемые поля.
    """
    update_data = data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не переданы данные для обновления",
        )

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)

    return current_user