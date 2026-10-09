"""
Тесты для auth-эндпоинтов.

Структура файла:
- регистрация (успех, дубликаты, валидация);
- логин (успех, неверный пароль, несуществующий email);
- /me (с токеном, без токена, с плохим токеном);
- refresh flow.

Все тесты используют фикстуры из conftest.py:
- client — TestClient с тестовой БД;
- test_user_data — данные для регистрации;
- registered_user — уже зарегистрированный пользователь;
- auth_headers — заголовки с access-токеном.
"""

# ---------- Регистрация ----------

def test_register_success(client, test_user_data):
    """Успешная регистрация нового пользователя."""
    response = client.post("/api/v1/auth/register", json=test_user_data)

    assert response.status_code == 201
    data = response.json()

    assert data["email"] == test_user_data["email"]
    assert data["username"] == test_user_data["username"]
    assert data["full_name"] == test_user_data["full_name"]
    assert data["role"] == "tester"  # роль по умолчанию
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data

    # КРИТИЧНО: hashed_password НЕ должен утекать в ответ
    assert "hashed_password" not in data
    assert "password" not in data


def test_register_duplicate_email(client, test_user_data, registered_user):
    """Повторная регистрация с тем же email — 409."""
    response = client.post("/api/v1/auth/register", json=test_user_data)

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_register_duplicate_username(client, test_user_data, registered_user):
    """Тот же username, но другой email — тоже 409."""
    new_data = {**test_user_data, "email": "other@qahub.io"}
    response = client.post("/api/v1/auth/register", json=new_data)

    assert response.status_code == 409
    assert "already taken" in response.json()["detail"]


def test_register_invalid_email(client, test_user_data):
    """Невалидный email — 422 (Pydantic)."""
    bad_data = {**test_user_data, "email": "not-an-email"}
    response = client.post("/api/v1/auth/register", json=bad_data)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("email" in err["loc"] for err in errors)


def test_register_short_password(client, test_user_data):
    """Пароль короче 8 символов — 422."""
    bad_data = {**test_user_data, "password": "short"}
    response = client.post("/api/v1/auth/register", json=bad_data)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("password" in err["loc"] for err in errors)


def test_register_short_username(client, test_user_data):
    """Username короче 3 символов — 422."""
    bad_data = {**test_user_data, "username": "ab"}
    response = client.post("/api/v1/auth/register", json=bad_data)

    assert response.status_code == 422


# ---------- Логин ----------

def test_login_success(client, test_user_data, registered_user):
    """Успешный логин возвращает пару токенов."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Оба токена — непустые строки
    assert len(data["access_token"]) > 20
    assert len(data["refresh_token"]) > 20


def test_login_wrong_password(client, test_user_data, registered_user):
    """Неверный пароль — 401."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user_data["email"],
            "password": "wrong_password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_email(client, test_user_data):
    """Email, которого нет в БД — 401 (тот же текст, чтобы не раскрывать)."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nobody@qahub.io",
            "password": "anypassword",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


# ---------- /me ----------

def test_me_with_token(client, auth_headers, test_user_data):
    """GET /me с валидным токеном возвращает данные текущего пользователя."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["email"] == test_user_data["email"]
    assert data["username"] == test_user_data["username"]
    assert "hashed_password" not in data


def test_me_without_token(client):
    """GET /me без токена — 401."""
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_with_invalid_token(client):
    """GET /me с мусорным токеном — 401."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )

    assert response.status_code == 401


def test_me_with_wrong_token_type(client):
    """Нельзя использовать refresh-токен как access — 401."""
    # Логинимся, чтобы получить refresh_token
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@qahub.io",
            "password": "testpass12345",
        },
    )
    # (в этом тесте мы не используем фикстуру auth_headers,
    # поэтому регистрируем пользователя вручную)
    if login_response.status_code != 200:
        # если ещё не зарегистрирован — регистрируем
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@qahub.io",
                "username": "testuser",
                "password": "testpass12345",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@qahub.io",
                "password": "testpass12345",
            },
        )

    refresh_token = login_response.json()["refresh_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert response.status_code == 401


# ---------- Refresh ----------

def test_refresh_success(client, test_user_data, registered_user):
    """Refresh возвращает пару токенов, и новый access работает."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        },
    )
    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Главная проверка: новый access-токен работает для /me
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == test_user_data["email"]



def test_refresh_with_invalid_token(client):
    """Невалидный refresh — 401."""
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )

    assert response.status_code == 401


def test_refresh_with_access_token(client, test_user_data, registered_user):
    """Нельзя использовать access-токен как refresh — 401."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        },
    )
    access_token = login_response.json()["access_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401
