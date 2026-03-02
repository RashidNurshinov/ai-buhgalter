"""
Сервис аутентификации: регистрация, вход, обновление токена.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → services/auth_service.py

Настройки пользователя объединены в таблицу users (без отдельной user_settings).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import TaxSystem
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenResponse


class AuthService:
    """Сервис аутентификации."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest) -> TokenResponse:
        """
        Регистрация нового пользователя.
        Возвращает TokenResponse с JWT-токенами или выбрасывает ValueError.
        """
        # Проверяем уникальность email
        existing = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("Пользователь с таким email уже существует")

        # Валидируем tax_system
        try:
            tax_system = TaxSystem(data.tax_system)
        except ValueError:
            tax_system = TaxSystem.USN_INCOME_EXPENSE

        # Создаём пользователя (настройки встроены в модель User)
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            inn=data.inn,
            business_name=data.business_name,
            tax_system=tax_system,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # Генерируем токены для автоматического входа после регистрации
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def login(self, email: str, password: str) -> TokenResponse:
        """
        Аутентификация по email/пароль.
        Возвращает TokenResponse или выбрасывает ValueError.
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError("Неверный email или пароль")

        if not verify_password(password, user.hashed_password):
            raise ValueError("Неверный email или пароль")

        if not user.is_active:
            raise ValueError("Аккаунт деактивирован")

        # Генерируем токены
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Обновление access-токена по refresh-токену.
        Возвращает новую пару токенов.
        """
        payload = decode_token(refresh_token)
        if payload is None:
            raise ValueError("Невалидный refresh-токен")

        token_type = payload.get("type")
        if token_type != "refresh":
            raise ValueError("Токен не является refresh-токеном")

        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("Невалидный refresh-токен")

        # Проверяем, что пользователь существует и активен
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError("Пользователь не найден")

        if not user.is_active:
            raise ValueError("Аккаунт деактивирован")

        # Генерируем новую пару токенов
        new_access_token = create_access_token(subject=str(user.id))
        new_refresh_token = create_refresh_token(subject=str(user.id))

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )