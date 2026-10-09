"""
Модуль безопасности: хеширование паролей и работа с JWT-токенами.

Здесь собраны все функции, связанные с:
- хешированием паролей (bcrypt через passlib);
- созданием access/refresh JWT-токенов (python-jose);
- декодированием и валидацией токенов.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


# CryptContext — это "менеджер схем хеширования" из passlib.
# Мы говорим: используй bcrypt для хеширования, и помечай устаревшие хеши,
# если они вдруг были сделаны другой схемой.
# deprecated="auto" означает: если в БД лежит старый хеш (например, sha256),
# passlib автоматически перехеширует его при следующем успешном логине.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Хеширует пароль.

    Что происходит:
    1. passlib генерирует случайную "соль" (salt) — добавляет её к паролю.
    2. Прогоняет результат через bcrypt (медленный, устойчивый к брутфорсу алгоритм).
    3. Возвращает строку вида: $2b$12$abc...xyz

    Почему нельзя хранить пароль в открытом виде:
    - Утечка БД = утечка всех паролей.
    - Пользователи часто используют один пароль на нескольких сайтах.

    Почему именно bcrypt:
    - Он намеренно медленный — подобрать пароль брутфорсом дорого.
    - Уже 20+ лет считается стандартом.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет пароль против хеша.

    Как это работает:
    - bcrypt не расшифровывает хеш (это невозможно).
    - Он берёт "соль" из хеша, хеширует введённый пароль с той же солью
      и сравнивает результат с хешем в БД.
    - Если совпало — пароль верный.

    Возвращает True/False.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Создаёт access-токен (JWT).

    Аргументы:
    - subject: обычно user.id (кем выдан токен). По стандарту JWT это поле "sub".
    - expires_delta: через сколько токен истечёт. Если None — берём из настроек.
    - extra_claims: любые дополнительные поля (например, {"role": "admin"}).

    Структура JWT:
    - header:  алгоритм и тип (HS256, JWT)
    - payload: данные (sub, exp, iat, роль и т.д.)
    - signature: HMAC-подпись всего выше нашим SECRET_KEY

    Любой может прочитать payload (он base64), но подделать подпись — нет.
    Поэтому НЕ кладём в токен пароли и секретные данные.
    """
    # Если время жизни не передали — берём из настроек
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # now(timezone.utc) — текущий момент в UTC. Это важно:
    # использовать наивное datetime.now() в токенах — плохая практика.
    now = datetime.now(timezone.utc)

    # payload — словарь, который уйдёт в токен
    # iat (issued at) — когда выдан
    # exp (expiration) — когда истекает
    # sub (subject) — кому выдан
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + expires_delta,
        "type": "access",
    }

    # Добавляем произвольные поля, если передали
    if extra_claims:
        payload.update(extra_claims)

    # jwt.encode — создаёт подписанный токен
    # Возвращает строку "xxxxx.yyyyy.zzzzz"
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Создаёт refresh-токен.

    Отличие от access-токена:
    - живёт дольше (обычно дни/недели, а не минуты);
    - используется только для получения нового access-токена;
    - НЕ даёт доступ к API напрямую.

    Поле "type": "refresh" нужно, чтобы при валидации не путать их местами.
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + expires_delta,
        "type": "refresh",
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    """
    Декодирует и валидирует JWT-токен.

    Что проверяется внутри jwt.decode:
    - подпись корректная (SECRET_KEY совпадает);
    - срок действия (exp) не истёк;
    - формат корректный.

    Что проверяем мы сами:
    - если expected_type задан, поле "type" должно ему соответствовать
      (чтобы access нельзя было использовать как refresh и наоборот).

    Если что-то не так — бросаем JWTError.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        # Пробрасываем выше — обработка будет в эндпоинте
        raise

    if expected_type is not None:
        token_type = payload.get("type")
        if token_type != expected_type:
            raise JWTError(f"Invalid token type: expected {expected_type}, got {token_type}")

    return payload
