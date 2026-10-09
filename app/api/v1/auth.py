"""
Эндпоинты аутентификации.

Каждый эндпоинт — это тонкая обёртка:
1. Принимает HTTP-запрос (валидация через Pydantic).
2. Вызывает сервис (бизнес-логика).
3. Преобразует доменные исключения в HTTPException.
4. Возвращает схему-ответ.

API-слой НЕ должен содержать бизнес-логику. Только «перевод» HTTP ↔ сервисы.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    authenticate_user,
    create_tokens,
    refresh_access_token,
    register_user,
)


# APIRouter — это «мини-приложение» FastAPI.
# Все эндпоинты, определённые на нём, будут подключены к основному app
# с общим префиксом и тегами (для Swagger).
router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать нового пользователя",
    responses={
        409: {"description": "Email или username уже заняты"},
    },
)
def register(
    user_in: UserCreate,
    db: DbSession,
) -> UserRead:
    """
    Регистрирует нового пользователя.

    Что делает:
    1. Pydantic валидирует вход (email, username, пароль ≥ 8 символов).
    2. Сервис проверяет уникальность email/username.
    3. Создаёт пользователя в БД.
    4. Возвращает данные пользователя (без hashed_password!).

    Возможные ошибки:
    - 422 Unprocessable Entity: невалидные данные (Pydantic).
    - 409 Conflict: email или username занят.
    """
    try:
        user = register_user(db, user_in)
    except UserAlreadyExistsError as e:
        # HTTPException — стандартный способ вернуть ошибку из FastAPI.
        # Он автоматически превратится в JSON {"detail": "..."}.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Войти по email и паролю",
    responses={
        401: {"description": "Неверный email или пароль"},
        403: {"description": "Аккаунт отключён"},
    },
)
def login(
    credentials: LoginRequest,
    db: DbSession,
) -> TokenResponse:
    """
    Аутентификация и выдача токенов.

    При успехе возвращает пару access + refresh.
    При неудаче — 401 (общий текст, не раскрываем, что именно неверно).

    Обрати внимание: в OpenAPI-схеме этот эндпоинт подключён к
    OAuth2PasswordBearer (в deps.py), что даёт кнопку Authorize в /docs.
    Однако наш эндпоинт принимает JSON, а не form-data.
    Для чисто Swagger-удобства можно сделать второй form-эндпоинт, но
    в реальной жизни JSON удобнее для мобильных/SPA-клиентов.
    """
    try:
        user = authenticate_user(db, credentials.email, credentials.password)
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InactiveUserError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    return create_tokens(user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновить access-токен по refresh-токену",
    responses={
        401: {"description": "Refresh-токен невалиден или истёк"},
        403: {"description": "Аккаунт отключён"},
    },
)
def refresh(
    body: RefreshRequest,
    db: DbSession,
) -> TokenResponse:
    """
    Выдаёт новую пару токенов по действующему refresh-токену.

    Зачем это нужно:
    - Access-токен живёт мало (30 мин). Когда он истёк, клиент шлёт refresh
      и получает новый access без повторного ввода пароля.
    - Если refresh тоже истёк (7 дней) — клиент вынужден логиниться заново.
    """
    try:
        return refresh_access_token(db, body.refresh_token)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InactiveUserError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Получить текущего пользователя",
    responses={
        401: {"description": "Невалидный или отсутствующий токен"},
    },
)
def read_me(current_user: CurrentUser) -> UserRead:
    """
    Возвращает данные текущего аутентифицированного пользователя.

    Всю работу делает зависимость get_current_user:
    - достаёт токен из заголовка Authorization;
    - валидирует;
    - находит пользователя в БД;
    - передаёт нам готовый объект.

    Если токен плохой — эндпоинт даже не вызовется, FastAPI вернёт 401.
    """
    return current_user
