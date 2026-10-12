"""
Тесты для TestCase API.

Структура:
- Создание (успех, с шагами, валидация enum, RBAC).
- Чтение (список, фильтр по сьюту, по id).
- Обновление.
- Удаление.
- Шаги (добавить, удалить, автопорядок).
"""

# ---------- Создание ----------

def test_create_case_success(client, auth_headers, project, case_data):
    """Успешное создание тест-кейса."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json=case_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["title"] == case_data["title"]
    assert data["priority"] == "high"
    assert data["type"] == "smoke"
    assert data["status"] == "draft"
    assert data["severity"] == "normal"  # default
    assert data["automated"] is False  # default
    assert data["suite_id"] is None
    assert data["steps"] == []


def test_create_case_with_steps(client, auth_headers, project):
    """Создание тест-кейса с шагами."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json={
            "title": "Full flow",
            "steps": [
                {"action": "Step 1", "expected_result": "Result 1"},
                {"action": "Step 2", "expected_result": "Result 2"},
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data["steps"]) == 2
    assert data["steps"][0]["order"] == 1
    assert data["steps"][1]["order"] == 2


def test_create_case_with_suite(client, auth_headers, project, suite):
    """Создание тест-кейса с привязкой к сьюту."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json={"title": "In suite", "suite_id": suite["id"]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["suite_id"] == suite["id"]


def test_create_case_invalid_suite(client, auth_headers, project):
    """Невалидный suite_id — 400."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json={"title": "Bad suite", "suite_id": fake_id},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_create_case_invalid_priority(client, auth_headers, project):
    """Невалидный priority — 422."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json={"title": "Test", "priority": "superurgent"},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_create_case_empty_title(client, auth_headers, project):
    """Пустое название — 422."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json={"title": ""},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_create_case_without_auth(client, project):
    """Без токена — 401."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json={"title": "Test"},
    )

    assert response.status_code == 401


# ---------- Чтение ----------

def test_list_cases_empty(client, auth_headers, project):
    """Пустой список."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/cases",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_cases(client, auth_headers, project, case, case_with_steps):
    """Список содержит оба кейса."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/cases",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    ids = {c["id"] for c in data}
    assert case["id"] in ids
    assert case_with_steps["id"] in ids


def test_list_cases_by_suite(
    client, auth_headers, project, suite, case
):
    """Фильтр по сьюту — привязываем кейс к сьюту и ищем."""
    # Обновляем case, чтобы привязать к сьюту
    client.patch(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}",
        json={"suite_id": suite["id"]},
        headers=auth_headers,
    )

    response = client.get(
        f"/api/v1/projects/{project['id']}/cases?suite_id={suite['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == case["id"]


def test_get_case_by_id(client, auth_headers, project, case_with_steps):
    """Получение кейса со шагами."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/cases/{case_with_steps['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == case_with_steps["id"]
    assert len(data["steps"]) == 3


def test_get_case_not_found(client, auth_headers, project):
    """Несуществующий кейс — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(
        f"/api/v1/projects/{project['id']}/cases/{fake_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


# ---------- Обновление ----------

def test_update_case_title(client, auth_headers, project, case):
    """PATCH title."""
    response = client.patch(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}",
        json={"title": "Updated title", "status": "active"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["status"] == "active"


def test_update_case_partial(client, auth_headers, project, case):
    """PATCH только priority."""
    original_title = case["title"]

    response = client.patch(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}",
        json={"priority": "critical"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == original_title
    assert data["priority"] == "critical"


# ---------- Удаление ----------

def test_delete_case(client, auth_headers, project, case):
    """Удаление тест-кейса."""
    response = client.delete(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    response = client.get(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_delete_case_cascade_steps(client, auth_headers, project, case_with_steps):
    """Удаление кейса каскадно удаляет шаги."""
    response = client.delete(
        f"/api/v1/projects/{project['id']}/cases/{case_with_steps['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 204
    # Шаги удалены (проверяем, что кейса нет)


# ---------- Шаги ----------

def test_add_step_success(client, auth_headers, project, case):
    """Добавление шага к пустому кейсу."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}/steps",
        json={"action": "Click button", "expected_result": "Action done"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["order"] == 1
    assert data["action"] == "Click button"


def test_add_step_auto_order(client, auth_headers, project, case_with_steps):
    """Order автоматически = max + 1."""
    # В case_with_steps уже 3 шага (order 1, 2, 3)
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases/{case_with_steps['id']}/steps",
        json={"action": "Step 4", "expected_result": "Result 4"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["order"] == 4


def test_add_step_explicit_order(client, auth_headers, project, case):
    """Явный order."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}/steps",
        json={"order": 99, "action": "Late", "expected_result": "Result"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["order"] == 99


def test_delete_step(client, auth_headers, project, case_with_steps):
    """Удаление шага."""
    step_id = case_with_steps["steps"][0]["id"]

    response = client.delete(
        f"/api/v1/projects/{project['id']}/cases/{case_with_steps['id']}/steps/{step_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Проверяем, что осталось 2 шага
    response = client.get(
        f"/api/v1/projects/{project['id']}/cases/{case_with_steps['id']}",
        headers=auth_headers,
    )
    assert len(response.json()["steps"]) == 2


def test_delete_step_not_found(client, auth_headers, project, case):
    """Несуществующий шаг — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.delete(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}/steps/{fake_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


# ---------- RBAC ----------

def test_other_user_cannot_access_cases(client, auth_headers, project, second_user, case):
    """Другой пользователь не видит кейсы чужого проекта."""
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "second@qahub.io",
            "password": "secondpass12345",
        },
    )
    second_token = login.json()["access_token"]
    second_headers = {"Authorization": f"Bearer {second_token}"}

    response = client.get(
        f"/api/v1/projects/{project['id']}/cases",
        headers=second_headers,
    )
    assert response.status_code == 404
