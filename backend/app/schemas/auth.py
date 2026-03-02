"""
Pydantic-схемы для аутентификации.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/auth.py
"""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Запрос на регистрацию."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Пароль (мин. 8 символов)")
    full_name: str = Field(..., min_length=2, max_length=255, description="ФИО")
    inn: str | None = Field(None, min_length=10, max_length=12, description="ИНН (10 или 12 цифр)")
    business_name: str | None = Field(None, max_length=500, description="Наименование бизнеса")
    tax_system: str = Field("usn_income_expense", description="Система налогообложения")


class LoginRequest(BaseModel):
    """Запрос на вход."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Ответ с JWT-токенами."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Запрос на обновление токена."""
    refresh_token: str