"""
API эндпоинты аутентификации: регистрация, вход, обновление токена.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → api/v1/auth.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Регистрация нового пользователя.
    Возвращает JWT-токены для автоматического входа.

    - **email** — уникальный email
    - **password** — пароль (мин. 8 символов)
    - **full_name** — ФИО
    - **inn** — ИНН предпринимателя (опционально)
    - **business_name** — название бизнеса (опционально)
    - **tax_system** — система налогообложения (по умолчанию usn_income_expense)
    """
    service = AuthService(db)
    try:
        tokens = await service.register(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    return tokens


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход в систему",
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Аутентификация по email/пароль.
    Возвращает access и refresh JWT-токены.
    """
    service = AuthService(db)
    try:
        tokens = await service.login(email=data.email, password=data.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновление токена",
)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Обновление access-токена по refresh-токену.
    Возвращает новую пару access + refresh токенов.
    """
    service = AuthService(db)
    try:
        tokens = await service.refresh_tokens(refresh_token=data.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return tokens


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Текущий пользователь",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Получить данные текущего авторизованного пользователя."""
    return current_user