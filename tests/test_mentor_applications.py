"""
Тесты для MentorApplication API.

Структура:
- Подача заявки (успех, RBAC, дубликат, валидация).
- Просмотр своих заявок.
- Отмена заявки.
- Админские операции: list, approve, reject.
- Проверка смены роли при одобрении.
"""

# ---------- Подача заявки ----------

def test_submit_application_success(client, guest_headers, application_data):
    """Успешная подача заявки GUEST-пользователем."""
    response = client.post(
        "/api/v1/mentor-applications",
        json=application_data,
        headers=guest_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["status"] == "pending"
    assert data["full_name"] == application_data["full_name"]
    assert data["experience_level"] == "1-3"
    assert data["tech_stack"] == ["pytest", "postman"]
    assert data["testing_types"] == ["functional", "regression"]
    assert data["reviewed_by"] is None
    assert data["reviewed_at"] is None
    assert data["rejection_reason"] is None


def test_submit_application_minimal(client, guest_headers):
    """Минимальный набор полей (только обязательные)."""
    response = client.post(
        "/api/v1/mentor-applications",
        json={"full_name": "Тест", "experience_level": "0-1"},
        headers=guest_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["github_url"] is None
    assert data["tech_stack"] is None


def test_submit_application_not_guest(
    client, auth_headers, application_data, db_session
):
    """Не-GUEST (student) не может подать заявку."""
    from app.crud.user import get_user_by_email
    from app.models.user import UserRole

    # Меняем роль через ту же сессию, что у API
    user = get_user_by_email(db_session, "test@qahub.io")
    if user:
        user.role = UserRole.STUDENT
        db_session.add(user)
        db_session.commit()

    response = client.post(
        "/api/v1/mentor-applications",
        json=application_data,
        headers=auth_headers,
    )

    assert response.status_code == 403
    assert "GUEST" in response.json()["detail"]

def test_submit_application_duplicate(client, guest_headers, application_data):
    """Повторная заявка от того же GUEST — 409."""
    # Первая заявка
    client.post(
        "/api/v1/mentor-applications",
        json=application_data,
        headers=guest_headers,
    )

    # Вторая заявка
    response = client.post(
        "/api/v1/mentor-applications",
        json=application_data,
        headers=guest_headers,
    )

    assert response.status_code == 409
    assert "active application" in response.json()["detail"].lower()


def test_submit_application_invalid_experience(client, guest_headers):
    """Невалидный experience_level — 422."""
    response = client.post(
        "/api/v1/mentor-applications",
        json={"full_name": "Тест", "experience_level": "10-20"},
        headers=guest_headers,
    )

    assert response.status_code == 422


def test_submit_application_invalid_url(client, guest_headers):
    """Невалидный GitHub URL — 422."""
    response = client.post(
        "/api/v1/mentor-applications",
        json={
            "full_name": "Тест",
            "experience_level": "1-3",
            "github_url": "not-a-url",
        },
        headers=guest_headers,
    )

    assert response.status_code == 422


def test_submit_application_without_auth(client, application_data):
    """Без токена — 401."""
    response = client.post(
        "/api/v1/mentor-applications",
        json=application_data,
    )

    assert response.status_code == 401


# ---------- Просмотр своих заявок ----------

def test_list_my_applications_empty(client, guest_headers):
    """Пустой список заявок."""
    response = client.get(
        "/api/v1/mentor-applications/my",
        headers=guest_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_my_applications(client, guest_headers, application):
    """Список с одной заявкой."""
    response = client.get(
        "/api/v1/mentor-applications/my",
        headers=guest_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == application["id"]


def test_get_my_active_application(client, guest_headers, application):
    """Активная заявка находится."""
    response = client.get(
        "/api/v1/mentor-applications/my/active",
        headers=guest_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == application["id"]


def test_get_my_active_application_none(client, guest_headers):
    """Если нет активной — null."""
    response = client.get(
        "/api/v1/mentor-applications/my/active",
        headers=guest_headers,
    )

    assert response.status_code == 200
    assert response.json() is None


# ---------- Отмена заявки ----------

def test_cancel_my_application(client, guest_headers, application):
    """GUEST может отменить свою pending-заявку."""
    response = client.delete(
        f"/api/v1/mentor-applications/{application['id']}",
        headers=guest_headers,
    )

    assert response.status_code == 204

    # Проверяем, что заявки больше нет
    list_response = client.get(
        "/api/v1/mentor-applications/my",
        headers=guest_headers,
    )
    assert list_response.json() == []


def test_cancel_application_not_found(client, guest_headers):
    """Несуществующая заявка — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.delete(
        f"/api/v1/mentor-applications/{fake_id}",
        headers=guest_headers,
    )

    assert response.status_code == 404


def test_cancel_application_not_pending(
    client, guest_headers, admin_headers, application
):
    """Нельзя отменить approved-заявку — 409."""
    # Админ одобряет
    client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/approve",
        headers=admin_headers,
    )

    # Пытаемся отменить
    response = client.delete(
        f"/api/v1/mentor-applications/{application['id']}",
        headers=guest_headers,
    )

    assert response.status_code == 409


# ---------- Админские: список ----------

def test_admin_list_applications_empty(client, admin_headers):
    """Список пустой у нового админа."""
    response = client.get(
        "/api/v1/admin/mentor-applications",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_admin_list_applications(client, admin_headers, application):
    """Список содержит заявку."""
    response = client.get(
        "/api/v1/admin/mentor-applications",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == application["id"]


def test_admin_list_filter_by_status(client, admin_headers, application):
    """Фильтр по статусу."""
    # По pending — есть
    response = client.get(
        "/api/v1/admin/mentor-applications?status=pending",
        headers=admin_headers,
    )
    assert len(response.json()) == 1

    # По approved — пусто
    response = client.get(
        "/api/v1/admin/mentor-applications?status=approved",
        headers=admin_headers,
    )
    assert response.json() == []


def test_admin_list_not_admin(client, guest_headers):
    """Не админ не видит список — 403."""
    response = client.get(
        "/api/v1/admin/mentor-applications",
        headers=guest_headers,
    )

    assert response.status_code == 403


# ---------- Админские: approve ----------

def test_admin_approve_application(client, admin_headers, application):
    """Одобрение заявки."""
    response = client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/approve",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["reviewed_by"] is not None
    assert data["reviewed_at"] is not None


def test_approve_changes_role_to_mentor(
    client, admin_headers, guest_headers, application
):
    """После одобрения роль пользователя становится MENTOR."""
    # Одобряем
    client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/approve",
        headers=admin_headers,
    )

    # Проверяем через /me
    response = client.get("/api/v1/auth/me", headers=guest_headers)
    # Токен старый — в нём роль ещё guest. Перелогинимся.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "guest_test@qahub.io", "password": "guest12345"},
    )
    new_token = login.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    response = client.get("/api/v1/auth/me", headers=new_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "mentor"


def test_approve_not_pending(client, admin_headers, application):
    """Повторное одобрение — 409."""
    # Первое одобрение
    client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/approve",
        headers=admin_headers,
    )

    # Второе
    response = client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/approve",
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_approve_not_found(client, admin_headers):
    """Несуществующая заявка — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/api/v1/admin/mentor-applications/{fake_id}/approve",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_approve_not_admin(client, guest_headers, application):
    """Не админ не может одобрять — 403."""
    response = client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/approve",
        headers=guest_headers,
    )

    assert response.status_code == 403


# ---------- Админские: reject ----------

def test_admin_reject_application(client, admin_headers, application):
    """Отклонение заявки."""
    response = client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/reject",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["reviewed_by"] is not None
    assert data["reviewed_at"] is not None


def test_reject_with_reason(client, admin_headers, application):
    """Отклонение с указанием причины."""
    import urllib.parse
    reason = urllib.parse.quote("Недостаточно опыта")

    response = client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/reject?rejection_reason={reason}",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["rejection_reason"] == "Недостаточно опыта"


def test_reject_does_not_change_role(
    client, admin_headers, guest_headers, application
):
    """Отклонение не меняет роль пользователя."""
    client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/reject",
        headers=admin_headers,
    )

    # Перелогинимся и проверим роль
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "guest_test@qahub.io", "password": "guest12345"},
    )
    new_token = login.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    response = client.get("/api/v1/auth/me", headers=new_headers)
    assert response.json()["role"] == "guest"


def test_reject_not_admin(client, guest_headers, application):
    """Не админ не может отклонять — 403."""
    response = client.post(
        f"/api/v1/admin/mentor-applications/{application['id']}/reject",
        headers=guest_headers,
    )

    assert response.status_code == 403
