"""
Pydantic-схемы для аутентификации.

Здесь только то, что связано с логином/токенами,
в отличие от schemas/user.py, где описание пользователя.
"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """
    Тело запроса на логин.

    Используем email как основной идентификатор — он уникален и однозначен.
    Пароль принимаем как обычную строку: валидировать его формат
    на логине бессмысленно — просто сравним с хешем.
    """

    email: EmailStr = Field(
        ...,
        description="Email пользователя",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Пароль",
        examples=["SecurePass123!"],
    )


class TokenResponse(BaseModel):
    """
    Ответ на успешный логин.

    Возвращаем пару токенов:
    - access_token — для запросов к API (короткий срок жизни, ~30 мин);
    - refresh_token — для получения нового access (длинный срок, ~7 дней).

    token_type = "bearer" — стандарт OAuth2. В заголовке Authorization
    клиент будет писать: "Bearer eyJhbGci...".
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """
    Тело запроса на обновление access-токена.

    Клиент присылает refresh_token, мы проверяем его и выдаём новую пару.
    Это называется "refresh flow".
    """

    refresh_token: str = Field(
        ...,
        description="Действующий refresh-токен",
    )
