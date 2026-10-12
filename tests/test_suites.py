"""
Тесты для TestSuite API.

Структура:
- Создание (успех, вложенные, валидация, RBAC).
- Чтение (список, дерево, по id, фильтры).
- Обновление.
- Удаление (с каскадом).
"""

# ---------- Создание ----------

def test_create_suite_success(client, auth_headers, project, suite_data):
    """Успешное создание сьюта."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json=suite_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == suite_data["name"]
    assert data["description"] == suite_data["description"]
    assert data["order"] == 0
    assert data["project_id"] == project["id"]
    assert data["parent_id"] is None
    assert "id" in data
    assert "created_by" in data


def test_create_child_suite(client, auth_headers, project, suite):
    """Создание вложенного сьюта с parent_id."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json={
            "name": "Password Reset",
            "parent_id": suite["id"],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "Password Reset"
    assert data["parent_id"] == suite["id"]


def test_create_suite_invalid_parent(client, auth_headers, project):
    """Parent сьют не существует — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json={"name": "Orphan", "parent_id": fake_id},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_create_suite_parent_from_other_project(
    client, auth_headers, project, second_user
):
    """Parent сьют из чужого проекта — 404."""
    # Создаём второй проект от того же пользователя
    second_project = client.post(
        "/api/v1/projects",
        json={"name": "Second", "key": "SEC"},
        headers=auth_headers,
    ).json()

    # Создаём сьют в первом проекте
    suite1 = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json={"name": "Suite 1"},
        headers=auth_headers,
    ).json()

    # Пытаемся использовать его как parent во втором проекте
    response = client.post(
        f"/api/v1/projects/{second_project['id']}/suites",
        json={"name": "Cross", "parent_id": suite1["id"]},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_create_suite_empty_name(client, auth_headers, project):
    """Пустое имя — 422."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json={"name": ""},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_create_suite_without_auth(client, project):
    """Без токена — 401."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json={"name": "Test"},
    )

    assert response.status_code == 401


# ---------- Чтение ----------

def test_list_suites_empty(client, auth_headers, project):
    """Пустой список сьютов."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_suites(client, auth_headers, project, suite, child_suite):
    """Плоский список — все сьюты проекта."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    ids = {s["id"] for s in data}
    assert suite["id"] in ids
    assert child_suite["id"] in ids


def test_list_only_roots(client, auth_headers, project, suite, child_suite):
    """only_roots=true — только корневые."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites?only_roots=true",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == suite["id"]
    assert data[0]["parent_id"] is None


def test_list_by_parent(client, auth_headers, project, suite, child_suite):
    """parent_id=UUID — только дети."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites?parent_id={suite['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == child_suite["id"]


def test_get_suite_tree(client, auth_headers, project, suite, child_suite):
    """Дерево: suite с одним child."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites/tree",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    root = data[0]
    assert root["id"] == suite["id"]
    assert len(root["children"]) == 1
    assert root["children"][0]["id"] == child_suite["id"]


def test_get_suite_tree_no_duplicates(client, auth_headers, project, suite, child_suite):
    """Дерево: child не должен дублироваться (регресс-тест)."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites/tree",
        headers=auth_headers,
    )

    data = response.json()
    children = data[0]["children"]

    # Проверяем, что нет дубликатов по id
    child_ids = [c["id"] for c in children]
    assert len(child_ids) == len(set(child_ids)), "Дубликат в children!"


def test_get_suite_by_id(client, auth_headers, project, suite):
    """Получение сьюта по id."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites/{suite['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == suite["id"]


def test_get_suite_not_found(client, auth_headers, project):
    """Несуществующий сьют — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(
        f"/api/v1/projects/{project['id']}/suites/{fake_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


# ---------- Обновление ----------

def test_update_suite_name(client, auth_headers, project, suite):
    """PATCH имени сьюта."""
    response = client.patch(
        f"/api/v1/projects/{project['id']}/suites/{suite['id']}",
        json={"name": "Updated Suite"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Suite"
    # description не менялся
    assert data["description"] == suite["description"]


def test_update_suite_partial(client, auth_headers, project, suite):
    """PATCH только description."""
    original_name = suite["name"]

    response = client.patch(
        f"/api/v1/projects/{project['id']}/suites/{suite['id']}",
        json={"description": "New description"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == original_name
    assert data["description"] == "New description"


# ---------- Удаление ----------

def test_delete_suite(client, auth_headers, project, suite):
    """Удаление сьюта."""
    response = client.delete(
        f"/api/v1/projects/{project['id']}/suites/{suite['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Проверяем, что сьюта больше нет
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites/{suite['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_delete_suite_cascade(client, auth_headers, project, suite, child_suite):
    """Удаление родителя каскадно удаляет детей."""
    response = client.delete(
        f"/api/v1/projects/{project['id']}/suites/{suite['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Ребёнок тоже удалён
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites/{child_suite['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------- RBAC ----------

def test_other_user_cannot_access_suites(client, auth_headers, project, second_user, suite):
    """Другой пользователь не видит сьюты чужого проекта."""
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

    # Список сьютов
    response = client.get(
        f"/api/v1/projects/{project['id']}/suites",
        headers=second_headers,
    )
    assert response.status_code == 404

    # Создать сьют
    response = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json={"name": "Hacked"},
        headers=second_headers,
    )
    assert response.status_code == 404
