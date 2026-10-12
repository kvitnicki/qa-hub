"""
Тесты для участников проекта.

Структура:
- Добавление участника.
- Список участников.
- Смена роли.
- Удаление участника (включая защиту owner'а).
- RBAC.
"""


# ---------- Добавление ----------

def test_add_member_success(client, auth_headers, project, second_user):
    """Успешное добавление участника."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": second_user["id"], "role": "tester"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["user_id"] == second_user["id"]
    assert data["role"] == "tester"
    assert data["project_id"] == project["id"]
    # Проверяем, что user вложен
    assert data["user"]["id"] == second_user["id"]
    assert data["user"]["username"] == "seconduser"


def test_add_member_default_role(client, auth_headers, project, second_user):
    """Роль по умолчанию — tester."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": second_user["id"]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["role"] == "tester"


def test_add_member_duplicate(client, auth_headers, project, second_user):
    """Повторное добавление — 409."""
    client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": second_user["id"], "role": "tester"},
        headers=auth_headers,
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": second_user["id"], "role": "tester"},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "already a member" in response.json()["detail"]


def test_add_member_nonexistent_user(client, auth_headers, project):
    """Несуществующий user_id — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": fake_id, "role": "tester"},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_add_member_invalid_role(client, auth_headers, project, second_user):
    """Невалидная роль — 422."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": second_user["id"], "role": "superuser"},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_add_member_not_owner(client, project, second_user, auth_headers):
    """
    Второй пользователь не owner — не может добавлять участников.

    Он даже не видит проект (404).
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

    # Пытаемся добавить участника в чужой проект
    response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": second_user["id"], "role": "tester"},
        headers=second_headers,
    )

    assert response.status_code in (403, 404)


# ---------- Список ----------

def test_list_members_only_owner(client, auth_headers, project):
    """В новом проекте только owner как qa_lead."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/members",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["role"] == "qa_lead"


def test_list_members_after_add(client, auth_headers, project, second_user):
    """После добавления — два участника."""
    client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": second_user["id"], "role": "tester"},
        headers=auth_headers,
    )

    response = client.get(
        f"/api/v1/projects/{project['id']}/members",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------- Смена роли ----------

def test_update_member_role(client, auth_headers, project, second_user):
    """Смена роли участника."""
    # Добавляем
    add_response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": second_user["id"], "role": "tester"},
        headers=auth_headers,
    )
    member_id = add_response.json()["id"]

    # Меняем роль
    response = client.patch(
        f"/api/v1/projects/{project['id']}/members/{member_id}",
        json={"role": "qa_lead"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["role"] == "qa_lead"


def test_update_member_role_not_found(client, auth_headers, project):
    """Несуществующий member_id — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.patch(
        f"/api/v1/projects/{project['id']}/members/{fake_id}",
        json={"role": "qa_lead"},
        headers=auth_headers,
    )

    assert response.status_code == 404


# ---------- Удаление ----------

def test_remove_member(client, auth_headers, project, second_user):
    """Удаление участника."""
    add_response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": second_user["id"], "role": "tester"},
        headers=auth_headers,
    )
    member_id = add_response.json()["id"]

    response = client.delete(
        f"/api/v1/projects/{project['id']}/members/{member_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Проверяем, что участников снова 1
    list_response = client.get(
        f"/api/v1/projects/{project['id']}/members",
        headers=auth_headers,
    )
    assert len(list_response.json()) == 1


def test_cannot_remove_owner(client, auth_headers, project):
    """Нельзя удалить owner'а — 403."""
    # Получаем member_id owner'а
    members = client.get(
        f"/api/v1/projects/{project['id']}/members",
        headers=auth_headers,
    ).json()
    owner_member_id = members[0]["id"]

    response = client.delete(
        f"/api/v1/projects/{project['id']}/members/{owner_member_id}",
        headers=auth_headers,
    )

    assert response.status_code == 403
    assert "owner" in response.json()["detail"].lower()
