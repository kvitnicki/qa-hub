"""
Общие фикстуры pytest для всех тестов.

conftest.py — специальный файл pytest. Фикстуры, определённые здесь,
автоматически доступны во всех тестовых файлах в той же папке и подпапках.

Ключевые концепции:
- Фикстуры — это функции-«поставщики» данных для тестов. pytest сам
  вызывает их, когда видит аргумент с тем же именем в тесте.
- scope задаёт «время жизни» фикстуры: function (по умолчанию),
  class, module, session.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app


# ---------- Тестовая БД ----------
#
# Используем ТУ ЖЕ PostgreSQL, но отдельную схему — "test".
# Схема в PostgreSQL — это как «пространство имён» для таблиц.
# Так dev и test данные не пересекаются, но и не нужен отдельный контейнер.

TEST_SCHEMA = "test"

TEST_DATABASE_URL = (
    f"{settings.DATABASE_URL}"
    f"?options=-csearch_path%3D{TEST_SCHEMA}"
)


@pytest.fixture(scope="session")
def test_engine():
    """
    Engine для тестовой БД.

    scope="session" означает: создаётся ОДИН раз на весь прогон тестов.
    Это правильно — engine тяжёлый (пул соединений), не нужно его
    пересоздавать для каждого теста.
    """
    engine = create_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)

    # Создаём схему test, если её нет
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}"))
        conn.commit()

    # Создаём все таблицы в схеме test по метаданным моделей
    Base.metadata.create_all(bind=engine)

    yield engine

    # Чистим после прогона
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """
    Сессия БД для одного теста.

    Как работает транзакционная изоляция:
    1. Открываем connection.
    2. Начинаем транзакцию (BEGIN).
    3. Создаём Session, привязанную к этому соединению.
    4. После теста — rollback всей транзакции.
       Все INSERT/UPDATE/DELETE откатятся, БД как до теста.

    Так тесты не влияют друг на друга и не оставляют мусор.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """
    HTTP-клиент для тестирования эндпоинтов.

    FastAPI TestClient позволяет делать запросы к приложению
    БЕЗ запуска сервера — всё в памяти, быстро.

    Ключевой момент: мы ПЕРЕОПРЕДЕЛЯЕМ зависимость get_db.
    Когда эндпоинт просит `db: DbSession`, FastAPI вызовет нашу
    override_get_db, которая возвращает ТУ ЖЕ сессию, что и в фикстуре.
    Это значит — изменения, сделанные через API, видны в тесте.
    """

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Возвращаем как было, чтобы не влиять на другие тесты
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Данные для регистрации тестового пользователя."""
    return {
        "email": "test@qahub.io",
        "username": "testuser",
        "password": "testpass12345",
        "full_name": "Test User",
    }


@pytest.fixture
def registered_user(client, test_user_data):
    """Регистрирует пользователя и возвращает его данные из API."""
    response = client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 201, f"Registration failed: {response.text}"
    return response.json()


@pytest.fixture
def auth_headers(client, test_user_data, registered_user):
    """
    Возвращает заголовки Authorization с валидным access-токеном.

    Использование в тесте:
        def test_something(client, auth_headers):
            response = client.get("/api/v1/auth/me", headers=auth_headers)
    """
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        },
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
