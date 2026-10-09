"""
CRUD-операции для модели User.

CRUD = Create, Read, Update, Delete.
Здесь только работа с БД — никакой бизнес-логики (она будет в services/).
Такое разделение упрощает тестирование и переиспользование.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """
    Находит пользователя по id.

    select(User).where(...) — это SQLAlchemy 2.0-style запросы.
    Раньше писали db.query(User).filter(...).first().
    Новый стиль более явный и лучше типизируется.

    .scalar_one_or_none() — вернёт одно значение или None (если не найдено).
    Если в БД вдруг окажется больше одного — упадёт с ошибкой (что хорошо:
    id уникален, дубликатов быть не может).
    """
    stmt = select(User).where(User.id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> User | None:
    """
    Находит пользователя по email.
    Нужен для логина и для проверки уникальности при регистрации.
    """
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_username(db: Session, username: str) -> User | None:
    """Находит пользователя по username."""
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    """
    Возвращает список пользователей с пагинацией.

    skip / limit — стандартный способ постраничной выдачи.
    Пример: skip=20, limit=10 → вернёт 21-30-го пользователя.

    order_by(User.created_at.desc()) — свежие вверху.
    """
    stmt = (
        select(User)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def create_user(db: Session, user_data: UserCreate) -> User:
    """
    Создаёт нового пользователя.

    Что происходит:
    1. Хешируем пароль (никогда не храним открытый!).
    2. Создаём ORM-объект User.
    3. db.add() — регистрируем объект в сессии (пока без SQL).
    4. db.commit() — отправляем INSERT в БД.
    5. db.refresh() — подтягиваем из БД сгенерированные значения (id, created_at).

    Почему именно такой порядок:
    - До commit'а объект живёт в памяти, но ещё не в БД.
    - После commit'а в БД есть запись, но поля, которые заполнила БД
      (server_default=func.now() для created_at, UUID default для id),
      в объекте ещё пусты — refresh() их подтянет.
    """
    db_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(
    db: Session,
    db_user: User,
    user_data: UserUpdate,
) -> User:
    """
    Обновляет пользователя.

    Принимает УЖЕ существующий ORM-объект (его надо было получить до вызова).
    user_data — Pydantic-схема с опциональными полями.

    Как работает:
    - user_data.model_dump(exclude_unset=True) возвращает dict только с теми
      полями, которые клиент явно передал (не считая default=None).
      Пример: {"full_name": "New Name"} — если клиент прислал только это.

    - Для каждого поля: setattr(объект, имя, значение).
    - Специальная обработка password: хешируем перед сохранением.
    """
    update_data = user_data.model_dump(exclude_unset=True)

    # Если пароль передан — хешируем перед сохранением
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, db_user: User) -> None:
    """
    Удаляет пользователя.

    db.delete() — помечает объект на удаление.
    commit() — выполняет DELETE в БД.

    После этого объект в памяти остаётся, но становится "detached".
    Если попробуешь обратиться к его полям — SQLAlchemy может упасть.
    """
    db.delete(db_user)
    db.commit()
