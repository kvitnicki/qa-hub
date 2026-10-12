"""
Тесты для Project API.

Структура:
- Создание проекта (успех, дубликаты, валидация).
- Чтение (список, по id, доступ).
- Обновление (PATCH, права).
- Удаление (права).
- Архивация.
- Права доступа (RBAC).
"""

# ---------- Создание ----------

def test_create_project_success(client, auth_headers, project_data):
    """Успешное создание проекта."""
    response = client.post(
        "/api/v1/projects",
        json=project_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == project_data["name"]
    assert data["key"] == project_data["key"]
    assert data["description"] == project_data["description"]
    assert data["is_archived"] is False
    assert "id" in data
    assert "owner_id" in data
    assert "created_at" in data


def test_create_project_duplicate_key(client, auth_headers, project_data, project):
    """Дубликат key — 409."""
    response = client.post(
        "/api/v1/projects",
        json=project_data,
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_create_project_invalid_key_lowercase(client, auth_headers, project_data):
    """key с маленькими буквами — 422."""
    bad_data = {**project_data, "key": "lowercase"}
    response = client.post(
        "/api/v1/projects",
        json=bad_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_create_project_short_key(client, auth_headers, project_data):
    """key короче 2 символов — 422."""
    bad_data = {**project_data, "key": "A"}
    response = client.post(
        "/api/v1/projects",
        json=bad_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_create_project_without_auth(client, project_data):
    """Без токена — 401."""
    response = client.post("/api/v1/projects", json=project_data)

    assert response.status_code == 401


# ---------- Чтение ----------

def test_list_projects_empty(client, auth_headers):
    """Пустой список проектов у нового пользователя."""
    response = client.get("/api/v1/projects", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_list_projects(client, auth_headers, project):
    """Список содержит созданный проект."""
    response = client.get("/api/v1/projects", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == project["id"]


def test_get_project_by_id(client, auth_headers, project):
    """GET проекта по id с участниками."""
    response = client.get(
        f"/api/v1/projects/{project['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == project["id"]
    assert data["key"] == "TEST"
    # Проверяем, что members есть и owner добавлен
    assert "members" in data
    assert len(data["members"]) == 1
    assert data["members"][0]["role"] == "qa_lead"


def test_get_project_not_found(client, auth_headers):
    """Несуществующий проект — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/projects/{fake_id}", headers=auth_headers)

    assert response.status_code == 404


def test_get_project_without_auth(client, project):
    """Без токена — 401."""
    response = client.get(f"/api/v1/projects/{project['id']}")

    assert response.status_code == 401


# ---------- Обновление ----------

def test_update_project_name(client, auth_headers, project):
    """PATCH имени проекта."""
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Updated Name"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    # key не менялся
    assert data["key"] == project["key"]


def test_update_project_partial(client, auth_headers, project):
    """PATCH только description, name не трогаем."""
    original_name = project["name"]

    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"description": "New description"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == original_name
    assert data["description"] == "New description"


# ---------- Архивация ----------

def test_archive_project(client, auth_headers, project):
    """Архивация проекта."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/archive",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["is_archived"] is True


def test_archived_not_in_default_list(client, auth_headers, project):
    """Архивные не показываются по умолчанию."""
    # Архивируем
    client.post(
        f"/api/v1/projects/{project['id']}/archive",
        headers=auth_headers,
    )

    # Список без архива
    response = client.get("/api/v1/projects", headers=auth_headers)
    assert response.json() == []

    # С include_archived=true — есть
    response = client.get(
        "/api/v1/projects?include_archived=true",
        headers=auth_headers,
    )
    assert len(response.json()) == 1


# ---------- Удаление ----------

def test_delete_project(client, auth_headers, project):
    """Удаление проекта."""
    response = client.delete(
        f"/api/v1/projects/{project['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Проверяем, что проекта больше нет
    response = client.get(
        f"/api/v1/projects/{project['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------- RBAC ----------

def test_other_user_cannot_see_project(
    client, auth_headers, second_user, project
):
    """
    Второй пользователь не участник проекта — не видит его.

    (В будущем можно расширить: возвращать 403, а не 404.
    Сейчас 404 — чтобы не раскрывать существование проекта.)
    """
    # Логинимся вторым пользователем
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "second@qahub.io",
            "password": "secondpass12345",
        },
    )
    second_token = login.json()["access_token"]
    second_headers = {"Authorization": f"Bearer {second_token}"}

    # Пытаемся получить чужой проект
    response = client.get(
        f"/api/v1/projects/{project['id']}",
        headers=second_headers,
    )

    assert response.status_code == 404


def test_other_user_cannot_update_project(
    client, auth_headers, second_user, project
):
    """Второй пользователь не может обновить чужой проект."""
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "second@qahub.io",
            "password": "secondpass12345",
        },
    )
    second_token = login.json()["access_token"]
    second_headers = {"Authorization": f"Bearer {second_token}"}

    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Hacked"},
        headers=second_headers,
    )

    # Owner check вернёт 404 (проект не найден) или 403 (не owner)
    assert response.status_code in (403, 404)


def test_other_user_cannot_delete_project(
    client, auth_headers, second_user, project
):
    """Второй пользователь не может удалить чужой проект."""
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "second@qahub.io",
            "password": "secondpass12345",
        },
    )
    second_token = login.json()["access_token"]
    second_headers = {"Authorization": f"Bearer {second_token}"}

    response = client.delete(
        f"/api/v1/projects/{project['id']}",
        headers=second_headers,
    )

    assert response.status_code in (403, 404)
