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

# ---------- Project fixtures ----------

@pytest.fixture
def project_data():
    """Данные для создания тестового проекта."""
    return {
        "name": "Test Project",
        "key": "TEST",
        "description": "Project for testing",
    }


@pytest.fixture
def project(client, auth_headers, project_data):
    """
    Создаёт проект через API и возвращает его данные.

    Использование:
        def test_something(client, project, auth_headers):
            project_id = project["id"]
    """
    response = client.post(
        "/api/v1/projects",
        json=project_data,
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Project creation failed: {response.text}"
    return response.json()


@pytest.fixture
def second_user_data():
    """Данные для второго пользователя (для тестов участников)."""
    return {
        "email": "second@qahub.io",
        "username": "seconduser",
        "password": "secondpass12345",
        "full_name": "Second User",
    }


@pytest.fixture
def second_user(client, second_user_data):
    """Создаёт второго пользователя и возвращает его данные."""
    response = client.post("/api/v1/auth/register", json=second_user_data)
    assert response.status_code == 201, f"Second user creation failed: {response.text}"
    return response.json()
# ---------- TestSuite fixtures ----------

@pytest.fixture
def suite_data():
    """Данные для создания тестового сьюта."""
    return {
        "name": "Login Tests",
        "description": "All login-related test cases",
        "order": 0,
    }


@pytest.fixture
def suite(client, auth_headers, project, suite_data):
    """Создаёт сьют через API и возвращает его данные."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json=suite_data,
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Suite creation failed: {response.text}"
    return response.json()


@pytest.fixture
def child_suite(client, auth_headers, project, suite):
    """Создаёт дочерний сьют (вложенный в suite)."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json={
            "name": "Password Reset",
            "description": "Child suite",
            "parent_id": suite["id"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Child suite creation failed: {response.text}"
    return response.json()


# ---------- TestCase fixtures ----------

@pytest.fixture
def case_data():
    """Данные для создания тест-кейса без шагов."""
    return {
        "title": "Login with valid credentials",
        "description": "Precondition: user exists",
        "priority": "high",
        "type": "smoke",
        "status": "draft",
    }


@pytest.fixture
def case(client, auth_headers, project, case_data):
    """Создаёт тест-кейс через API и возвращает его данные."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json=case_data,
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Case creation failed: {response.text}"
    return response.json()


@pytest.fixture
def case_with_steps(client, auth_headers, project):
    """Создаёт тест-кейс с 3 шагами."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json={
            "title": "Full login flow",
            "priority": "critical",
            "type": "e2e",
            "steps": [
                {
                    "action": "Open /login page",
                    "expected_result": "Page loads",
                },
                {
                    "action": "Enter credentials",
                    "expected_result": "Form submitted",
                },
                {
                    "action": "Check redirect",
                    "expected_result": "Dashboard opens",
                },
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Case with steps failed: {response.text}"
    return response.json()



# ---------- TestRun fixtures ----------

@pytest.fixture
def run_data(case, case_with_steps):
    """Данные для создания тестового прогона с двумя кейсами."""
    return {
        "name": "Test Run",
        "environment": "staging",
        "source": "manual",
        "test_case_ids": [case["id"], case_with_steps["id"]],
    }


@pytest.fixture
def run(client, auth_headers, project, run_data):
    """Создаёт прогон через API и возвращает его данные (без результатов)."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json=run_data,
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Run creation failed: {response.text}"
    return response.json()


@pytest.fixture
def run_with_results(client, auth_headers, project, run):
    """Возвращает прогон со всеми результатами (из GET /runs/{id})."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200, f"Run fetch failed: {response.text}"
    return response.json()


@pytest.fixture
def completed_run(client, auth_headers, project, run_with_results):
    """
    Прогон с двумя результатами: passed + failed.

    Должен автоматически стать completed.
    """
    results = run_with_results["results"]
    run_id = run_with_results["id"]

    # Обновляем первый результат: passed
    client.patch(
        f"/api/v1/projects/{project['id']}/runs/{run_id}/results/{results[0]['id']}",
        json={"status": "passed", "duration_ms": 1200},
        headers=auth_headers,
    )

    # Обновляем второй: failed
    client.patch(
        f"/api/v1/projects/{project['id']}/runs/{run_id}/results/{results[1]['id']}",
        json={"status": "failed", "duration_ms": 3500, "comment": "Timeout"},
        headers=auth_headers,
    )

    # Возвращаем актуальное состояние
    response = client.get(
        f"/api/v1/projects/{project['id']}/runs/{run_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()
