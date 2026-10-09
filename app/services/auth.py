"""
Бизнес-логика аутентификации.

Слой services отвечает за:
- правила бизнеса (например, "email должен быть уникален");
- оркестрацию (несколько вызовов CRUD + security);
- возврат доменных исключений, которые API превратит в HTTP-ошибки.

Слой crud — только SQL. Слой services — только логика.
API — только HTTP. Это называется "слоистая архитектура".
"""

import uuid

from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate


class AuthError(Exception):
    """Базовое исключение для ошибок аутентификации."""


class UserAlreadyExistsError(AuthError):
    """Пользователь с таким email или username уже есть."""


class InvalidCredentialsError(AuthError):
    """Неверный email или пароль."""


class InactiveUserError(AuthError):
    """Пользователь найден, но его аккаунт отключён."""


class InvalidTokenError(AuthError):
    """Токен невалиден, истёк или имеет неверный тип."""


def register_user(db: Session, user_data: UserCreate) -> User:
    """Регистрирует нового пользователя с проверкой уникальности."""
    existing_email = user_crud.get_user_by_email(db, user_data.email)
    if existing_email is not None:
        raise UserAlreadyExistsError(f"Email '{user_data.email}' is already registered")

    existing_username = user_crud.get_user_by_username(db, user_data.username)
    if existing_username is not None:
        raise UserAlreadyExistsError(f"Username '{user_data.username}' is already taken")

    return user_crud.create_user(db, user_data)


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Проверяет email + пароль. Возвращает User или бросает исключение."""
    user = user_crud.get_user_by_email(db, email)

    if user is None:
        raise InvalidCredentialsError("Invalid email or password")

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid email or password")

    if not user.is_active:
        raise InactiveUserError("User account is disabled")

    return user


def create_tokens(user: User) -> TokenResponse:
    """Создаёт пару access + refresh для пользователя."""
    access = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role.value},
    )
    refresh = create_refresh_token(subject=str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)


def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
    """Обновляет access-токен по refresh-токену."""
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except JWTError as e:
        raise InvalidTokenError("Invalid or expired refresh token") from e

    subject = payload.get("sub")
    if subject is None:
        raise InvalidTokenError("Token has no subject")

    try:
        user_id = uuid.UUID(subject)
    except ValueError as e:
        raise InvalidTokenError("Malformed subject in token") from e

    user = user_crud.get_user_by_id(db, user_id)
    if user is None:
        raise InvalidTokenError("User from token not found")

    if not user.is_active:
        raise InactiveUserError("User account is disabled")

    return create_tokens(user)
