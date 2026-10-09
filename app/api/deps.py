"""
FastAPI-зависимости (dependencies).

Depends() в FastAPI — это механизм "внедрения зависимостей" (DI).
Ты объявляешь функцию, которая готовит данные, и FastAPI сам вызывает её
перед эндпоинтом, передавая результат в аргумент.

Пример в эндпоинте:
    @router.get("/me")
    def me(current_user: User = Depends(get_current_user)):
        return current_user

Здесь get_current_user — зависимость, которая:
1. Достаёт токен из заголовка Authorization.
2. Проверяет подпись.
3. Находит пользователя в БД.
4. Возвращает его в эндпоинт.

Если что-то не так (нет токена, истёк, пользователь удалён) — FastAPI
автоматически вернёт 401, а эндпоинт даже не вызовется.
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.crud import user as user_crud
from app.models.user import User, UserRole


# OAuth2PasswordBearer — это схема безопасности для Swagger.
# tokenUrl — эндпоинт, куда Swagger отправит логин/пароль, чтобы получить токен.
# Мы укажем /api/v1/auth/login (создадим позже).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# Annotated — это "обёртка" для типа из PEP 593.
# Она позволяет приписать к типу метаданные, не меняя сам тип.
# FastAPI читает эти метаданные и понимает: "тут Depends(get_db)".
# Преимущество перед Depends(...) в аргументе: чище и переиспользуемо.
DbSession = Annotated[Session, Depends(get_db)]
TokenStr = Annotated[str, Depends(oauth2_scheme)]


def get_current_user(db: DbSession, token: TokenStr) -> User:
    """
    Достаёт текущего пользователя из JWT.

    Как работает:
    1. FastAPI передаёт нам сессию БД и сам токен из заголовка
       Authorization: Bearer <token>.
    2. Декодируем токен. Если невалиден — 401.
    3. Достаём sub (user id) из payload.
    4. Ищем пользователя в БД по id.
    5. Если не нашли или is_active=False — 401.

    Возвращаем ORM-объект User.
    """
    # Единый текст ошибки: не раскрываем, что именно не так (нет токена / истёк / не найден).
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token, expected_type="access")
    except JWTError:
        raise credentials_exception

    subject = payload.get("sub")
    if subject is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_exception

    user = user_crud.get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


# Аналогично DbSession/TokenStr — удобные алиасы
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: UserRole):
    """
    Фабрика зависимостей для проверки ролей.

    Использование в эндпоинте:
        @router.delete("/users/{id}", dependencies=[Depends(require_role(UserRole.ADMIN))])
        def delete_user(...): ...

    Или как параметр:
        def delete_user(_: User = Depends(require_role(UserRole.ADMIN))): ...

    Как работает:
    - require_role(...) возвращает внутреннюю функцию-зависимость.
    - Внутри неё FastAPI передаёт current_user (благодаря CurrentUser).
    - Если роль пользователя не в списке — 403 Forbidden.

    Это паттерн "фабрика зависимостей" — очень гибкий способ
    переиспользовать одну и ту же логику с разными параметрами.
    """
    def role_checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker
