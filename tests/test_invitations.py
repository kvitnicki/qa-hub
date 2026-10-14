"""
Тесты для Invitation API.
"""

import uuid

# ---------- Создание ----------

def test_create_invitation_success(
    client, mentor_headers, cohort, invitation_data
):
    """MENTOR создаёт приглашение."""
    response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/invitations",
        json=invitation_data,
        headers=mentor_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["email"] == invitation_data["email"]
    assert data["status"] == "pending"
    assert data["message"] == invitation_data["message"]
    assert data["accepted_at"] is None
    assert "token" not in data  # токен не светим
    assert "expires_at" in data


def test_create_invitation_not_mentor(
    client, auth_headers, cohort, invitation_data
):
    """Обычный пользователь не может создать приглашение."""
    response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/invitations",
        json=invitation_data,
        headers=auth_headers,
    )

    assert response.status_code == 403


def test_create_invitation_duplicate(
    client, mentor_headers, cohort, invitation_data, invitation
):
    """Дубликат pending-приглашения — 409."""
    response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/invitations",
        json=invitation_data,
        headers=mentor_headers,
    )

    assert response.status_code == 409
    assert "already" in response.json()["detail"].lower()


def test_create_invitation_email_is_student(
    client, mentor_headers, cohort, student_user
):
    """
    Email уже студент (в любой когорте) — 409.

    student_user — это созданный STUDENT через фикстуру.
    """
    response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/invitations",
        json={"email": student_user["email"]},
        headers=mentor_headers,
    )

    assert response.status_code == 409
    assert "already a student" in response.json()["detail"]


def test_create_invitation_empty_email(client, mentor_headers, cohort):
    """Пустой email — 422."""
    response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/invitations",
        json={"email": ""},
        headers=mentor_headers,
    )

    assert response.status_code == 422


def test_create_invitation_cohort_not_found(client, mentor_headers):
    """Несуществующая когорта — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/api/v1/cohorts/{fake_id}/invitations",
        json={"email": "test@qahub.io"},
        headers=mentor_headers,
    )

    assert response.status_code == 404


# ---------- Список ----------

def test_list_invitations_empty(client, mentor_headers, cohort):
    """Пустой список приглашений."""
    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}/invitations",
        headers=mentor_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_invitations(client, mentor_headers, cohort, invitation):
    """Список содержит приглашение."""
    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}/invitations",
        headers=mentor_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == invitation["id"]


def test_list_invitations_filter_status(
    client, mentor_headers, cohort, invitation
):
    """Фильтр по статусу."""
    # pending — есть
    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}/invitations?status=pending",
        headers=mentor_headers,
    )
    assert len(response.json()) == 1

    # accepted — пусто
    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}/invitations?status=accepted",
        headers=mentor_headers,
    )
    assert response.json() == []


def test_list_invitations_not_owner(
    client, auth_headers, cohort, invitation
):
    """Другой пользователь не видит приглашения — 403."""
    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}/invitations",
        headers=auth_headers,
    )

    assert response.status_code == 403


# ---------- My Invitations ----------

def test_my_invitations_empty(client, invited_student_token):
    """Пока нет приглашений — пусто."""
    response = client.get(
        "/api/v1/my/invitations",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_my_invitations(
    client, invitation, invited_student_token
):
    """Приглашение видно приглашённому."""
    response = client.get(
        "/api/v1/my/invitations",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["email"] == invitation["email"]
    assert data[0]["status"] == "pending"


# ---------- Публичная информация ----------

def test_public_info(client, invitation, db_session):
    """Публичная информация по токену."""
    from app.crud.invitation import get_invitation_by_id

    db_inv = get_invitation_by_id(db_session, uuid.UUID(invitation["id"]))
    token = db_inv.token

    response = client.get(f"/api/v1/invitations/info/{token}")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == invitation["email"]
    assert data["cohort_name"] == "QA-2026-Осень"
    assert data["mentor_username"] == "mentor_test"
    assert data["is_expired"] is False


def test_public_info_invalid_token(client):
    """Несуществующий токен — 404."""
    response = client.get("/api/v1/invitations/info/invalid-token")

    assert response.status_code == 404


# ---------- Принятие ----------

def test_accept_invitation_success(
    client, invitation, invited_student_token, db_session
):
    """Успешное принятие приглашения."""
    from app.crud.invitation import get_invitation_by_id

    db_inv = get_invitation_by_id(db_session, uuid.UUID(invitation["id"]))
    token = db_inv.token

    response = client.post(
        f"/api/v1/invitations/accept/{token}",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["cohort_name"] == "QA-2026-Осень"


def test_accept_changes_role_to_student(
    client, invitation, invited_student_token, db_session
):
    """После принятия роль меняется на STUDENT."""
    from app.crud.invitation import get_invitation_by_id

    db_inv = get_invitation_by_id(db_session, uuid.UUID(invitation["id"]))

    client.post(
        f"/api/v1/invitations/accept/{db_inv.token}",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )

    # Перелогинимся
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "invited_student@qahub.io", "password": "student12345"},
    )
    new_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/v1/auth/me", headers=new_headers)
    assert response.json()["role"] == "student"


def test_accept_twice(client, invitation, invited_student_token, db_session):
    """Повторное принятие — 409."""
    from app.crud.invitation import get_invitation_by_id

    db_inv = get_invitation_by_id(db_session, uuid.UUID(invitation["id"]))

    client.post(
        f"/api/v1/invitations/accept/{db_inv.token}",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )

    response = client.post(
        f"/api/v1/invitations/accept/{db_inv.token}",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )

    assert response.status_code == 409
    assert "already" in response.json()["detail"].lower()


def test_accept_email_mismatch(
    client, invitation, auth_headers, db_session
):
    """Принятие чужого приглашения — 400."""
    from app.crud.invitation import get_invitation_by_id

    db_inv = get_invitation_by_id(db_session, uuid.UUID(invitation["id"]))

    # auth_headers — это test@qahub.io, а приглашение на invited_student@qahub.io
    response = client.post(
        f"/api/v1/invitations/accept/{db_inv.token}",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


def test_accept_invalid_token(client, invited_student_token):
    """Несуществующий токен — 404."""
    response = client.post(
        "/api/v1/invitations/accept/invalid-token-here",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )

    assert response.status_code == 404


def test_accept_without_auth(client, invitation, db_session):
    """Без токена — 401."""
    from app.crud.invitation import get_invitation_by_id

    db_inv = get_invitation_by_id(db_session, uuid.UUID(invitation["id"]))

    response = client.post(f"/api/v1/invitations/accept/{db_inv.token}")

    assert response.status_code == 401


# ---------- Отклонение ----------

def test_decline_invitation_success(
    client, invitation, invited_student_token, db_session
):
    """Успешное отклонение."""
    from app.crud.invitation import get_invitation_by_id

    db_inv = get_invitation_by_id(db_session, uuid.UUID(invitation["id"]))

    response = client.post(
        f"/api/v1/invitations/decline/{db_inv.token}",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "declined"


def test_decline_does_not_change_role(
    client, invitation, invited_student_token, db_session
):
    """После отклонения роль остаётся GUEST."""
    from app.crud.invitation import get_invitation_by_id

    db_inv = get_invitation_by_id(db_session, uuid.UUID(invitation["id"]))

    client.post(
        f"/api/v1/invitations/decline/{db_inv.token}",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {invited_student_token}"},
    )
    assert response.json()["role"] == "guest"


def test_decline_email_mismatch(
    client, invitation, auth_headers, db_session
):
    """Отклонение чужого приглашения — 400."""
    from app.crud.invitation import get_invitation_by_id

    db_inv = get_invitation_by_id(db_session, uuid.UUID(invitation["id"]))

    response = client.post(
        f"/api/v1/invitations/decline/{db_inv.token}",
        headers=auth_headers,
    )

    assert response.status_code == 400


# ---------- Отзыв ----------

def test_revoke_invitation(client, mentor_headers, invitation):
    """MENTOR отзывает своё pending-приглашение."""
    response = client.delete(
        f"/api/v1/invitations/{invitation['id']}",
        headers=mentor_headers,
    )

    assert response.status_code == 204


def test_revoke_not_owner(
    client, auth_headers, invitation
):
    """Не владелец не может отозвать — 403."""
    response = client.delete(
        f"/api/v1/invitations/{invitation['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 403
