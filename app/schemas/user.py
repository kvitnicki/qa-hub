"""
Pydantic-схемы для модели User.

Схемы — это "контракт" API:
- что клиент может прислать (request body);
- что мы возвращаем (response body);
- как валидируются данные.

Схемы ≠ модели БД. Модель User (SQLAlchemy) — для хранения.
Схемы (Pydantic) — для обмена данными по HTTP.
Это называется "разделение слоёв" (separation of concerns).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


# ---------- Базовые схемы ----------

class UserBase(BaseModel):
    """
    Общие поля для всех схем User.

    Наследование в Pydantic работает как в обычном Python:
    дочерние схемы получают все поля родителя и добавляют свои.
    """

    email: EmailStr = Field(
        ...,
        description="Email пользователя",
        examples=["user@example.com"],
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Уникальное имя пользователя",
        examples=["john_doe"],
    )
    full_name: str | None = Field(
        default=None,
        max_length=100,
        description="Полное имя (опционально)",
        examples=["John Doe"],
    )


class UserCreate(UserBase):
    """
    Схема для регистрации нового пользователя.

    Наследует email, username, full_name от UserBase.
    Добавляет пароль — он нужен только при создании, но НЕ в ответах.
    """

    password: str = Field(
        ...,
        min_length=8,
        max_length=72,  # Ограничение bcrypt — 72 байта
        description="Пароль (минимум 8 символов)",
        examples=["SecurePass123!"],
    )
    role: UserRole = Field(
        default=UserRole.TESTER,
        description="Роль пользователя",
    )


class UserUpdate(BaseModel):
    """
    Схема для обновления пользователя (PATCH).

    ВСЕ поля опциональны — клиент может обновить только часть.
    Например: {"full_name": "New Name"} — обновит только имя.
    Остальные останутся как были.
    """

    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=50)
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    role: UserRole | None = None
    is_active: bool | None = None


# ---------- Схемы для чтения (response) ----------

class UserRead(UserBase):
    """
    Схема для возврата пользователя по API.

    Наследует email, username, full_name от UserBase.
    Добавляет id, role, is_active, created_at, updated_at.
    НЕ содержит hashed_password — никогда не отдаём его наружу.

    model_config = ConfigDict(from_attributes=True) позволяет создавать
    схему из ORM-объекта:
        user_read = UserRead.model_validate(user_orm_obj)
    Без этой настройки Pydantic не сможет прочитать атрибуты SQLAlchemy-модели.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserShort(BaseModel):
    """
    Короткая версия User для вложенных ответов.

    Когда возвращаем, например, проект со списком участников,
    не нужно тянуть все поля. Достаточно id и username.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    full_name: str | None = None
    role: UserRole
