"""
Тесты для Cohort и CohortMember API.

Структура:
- Создание когорты (успех, RBAC, валидация).
- Чтение (список, по id, архивные).
- Обновление, архивация, удаление.
- Участники (добавление, дубликаты, partial unique, защита владельца).
- Статистика.
"""

# ---------- Создание ----------

def test_create_cohort_success(client, mentor_headers, cohort_data):
    """MENTOR может создать когорту."""
    response = client.post(
        "/api/v1/cohorts",
        json=cohort_data,
        headers=mentor_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == cohort_data["name"]
    assert data["description"] == cohort_data["description"]
    assert data["is_archived"] is False
    assert "id" in data
    assert "mentor_id" in data


def test_create_cohort_as_admin(client, admin_headers, cohort_data):
    """ADMIN тоже может создавать когорты."""
    response = client.post(
        "/api/v1/cohorts",
        json=cohort_data,
        headers=admin_headers,
    )

    assert response.status_code == 201


def test_create_cohort_not_mentor(client, auth_headers, cohort_data):
    """Обычный GUEST/STUDENT не может создать когорту."""
    response = client.post(
        "/api/v1/cohorts",
        json=cohort_data,
        headers=auth_headers,
    )

    assert response.status_code == 403
    assert "MENTOR" in response.json()["detail"]


def test_create_cohort_without_auth(client, cohort_data):
    """Без токена — 401."""
    response = client.post(
        "/api/v1/cohorts",
        json=cohort_data,
    )

    assert response.status_code == 401


def test_create_cohort_empty_name(client, mentor_headers):
    """Пустое имя — 422."""
    response = client.post(
        "/api/v1/cohorts",
        json={"name": ""},
        headers=mentor_headers,
    )

    assert response.status_code == 422


# ---------- Чтение ----------

def test_list_cohorts_empty(client, mentor_headers):
    """Пустой список когорт."""
    response = client.get(
        "/api/v1/cohorts",
        headers=mentor_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_cohorts(client, mentor_headers, cohort):
    """Список содержит созданную когорту."""
    response = client.get(
        "/api/v1/cohorts",
        headers=mentor_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == cohort["id"]


def test_get_cohort_with_members(client, mentor_headers, cohort):
    """Когорта с участниками — mentor автоматически добавлен."""
    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}",
        headers=mentor_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["members"]) == 1
    assert data["members"][0]["role"] == "mentor"


def test_get_cohort_not_found(client, mentor_headers):
    """Несуществующая когорта — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(
        f"/api/v1/cohorts/{fake_id}",
        headers=mentor_headers,
    )

    assert response.status_code == 404


# ---------- Обновление ----------

def test_update_cohort_name(client, mentor_headers, cohort):
    """PATCH имени когорты."""
    response = client.patch(
        f"/api/v1/cohorts/{cohort['id']}",
        json={"name": "Переименованная когорта"},
        headers=mentor_headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Переименованная когорта"


def test_update_cohort_partial(client, mentor_headers, cohort):
    """PATCH только description."""
    original_name = cohort["name"]

    response = client.patch(
        f"/api/v1/cohorts/{cohort['id']}",
        json={"description": "Новое описание"},
        headers=mentor_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == original_name
    assert data["description"] == "Новое описание"


# ---------- Архивация ----------

def test_archive_cohort(client, mentor_headers, cohort):
    """Архивация когорты."""
    response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/archive",
        headers=mentor_headers,
    )

    assert response.status_code == 200
    assert response.json()["is_archived"] is True


def test_archived_not_in_default_list(client, mentor_headers, cohort):
    """Архивные скрыты по умолчанию."""
    # Архивируем
    client.post(
        f"/api/v1/cohorts/{cohort['id']}/archive",
        headers=mentor_headers,
    )

    # По умолчанию — пусто
    response = client.get("/api/v1/cohorts", headers=mentor_headers)
    assert response.json() == []

    # С include_archived=true — есть
    response = client.get(
        "/api/v1/cohorts?include_archived=true",
        headers=mentor_headers,
    )
    assert len(response.json()) == 1


# ---------- Удаление ----------

def test_delete_cohort(client, mentor_headers, cohort):
    """Удаление когорты."""
    response = client.delete(
        f"/api/v1/cohorts/{cohort['id']}",
        headers=mentor_headers,
    )

    assert response.status_code == 204

    # Проверяем, что нет
    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}",
        headers=mentor_headers,
    )
    assert response.status_code == 404


# ---------- Участники ----------

def test_add_student(client, mentor_headers, cohort, student_user):
    """Добавление студента в когорту."""
    response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/members",
        json={"user_id": student_user["id"], "role": "student"},
        headers=mentor_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == student_user["id"]
    assert data["role"] == "student"
    assert data["user"]["username"] == "student_test"


def test_add_student_duplicate(client, mentor_headers, cohort, student_user):
    """Повторное добавление — 409."""
    client.post(
        f"/api/v1/cohorts/{cohort['id']}/members",
        json={"user_id": student_user["id"], "role": "student"},
        headers=mentor_headers,
    )

    response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/members",
        json={"user_id": student_user["id"], "role": "student"},
        headers=mentor_headers,
    )

    assert response.status_code == 409
    assert "already a member" in response.json()["detail"]


def test_add_student_to_second_cohort(
    client, mentor_headers, cohort, student_user, cohort_data
):
    """Студент не может быть в двух когортах — 409 (partial unique)."""
    # Добавляем в первую когорту
    client.post(
        f"/api/v1/cohorts/{cohort['id']}/members",
        json={"user_id": student_user["id"], "role": "student"},
        headers=mentor_headers,
    )

    # Создаём вторую когорту
    cohort2 = client.post(
        "/api/v1/cohorts",
        json={"name": "Вторая когорта"},
        headers=mentor_headers,
    ).json()

    # Пытаемся добавить туда же студента
    response = client.post(
        f"/api/v1/cohorts/{cohort2['id']}/members",
        json={"user_id": student_user["id"], "role": "student"},
        headers=mentor_headers,
    )

    assert response.status_code == 409
    assert "already a student in another cohort" in response.json()["detail"]


def test_add_nonexistent_user(client, mentor_headers, cohort):
    """Несуществующий user — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/members",
        json={"user_id": fake_id, "role": "student"},
        headers=mentor_headers,
    )

    assert response.status_code == 404


def test_list_members(client, mentor_headers, cohort, student_user):
    """Список участников когорты."""
    client.post(
        f"/api/v1/cohorts/{cohort['id']}/members",
        json={"user_id": student_user["id"], "role": "student"},
        headers=mentor_headers,
    )

    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}/members",
        headers=mentor_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # mentor + student

    roles = {m["role"] for m in data}
    assert roles == {"mentor", "student"}


def test_remove_member(client, mentor_headers, cohort, student_user):
    """Удаление студента из когорты."""
    # Добавляем
    add_response = client.post(
        f"/api/v1/cohorts/{cohort['id']}/members",
        json={"user_id": student_user["id"], "role": "student"},
        headers=mentor_headers,
    )
    member_id = add_response.json()["id"]

    # Удаляем
    response = client.delete(
        f"/api/v1/cohorts/{cohort['id']}/members/{member_id}",
        headers=mentor_headers,
    )

    assert response.status_code == 204


def test_cannot_remove_owner(client, mentor_headers, cohort):
    """Владельца-ментора удалить нельзя — 400."""
    # Получаем member_id ментора
    members = client.get(
        f"/api/v1/cohorts/{cohort['id']}/members",
        headers=mentor_headers,
    ).json()
    mentor_member_id = members[0]["id"]

    response = client.delete(
        f"/api/v1/cohorts/{cohort['id']}/members/{mentor_member_id}",
        headers=mentor_headers,
    )

    assert response.status_code == 400
    assert "owner" in response.json()["detail"].lower()


# ---------- Статистика ----------

def test_cohort_stats_empty(client, mentor_headers, cohort):
    """Статистика пустой когорты (только ментор)."""
    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}/stats",
        headers=mentor_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_students"] == 0
    assert data["total_mentors"] == 1
    assert data["max_students"] == 5
    assert data["is_full"] is False


def test_cohort_stats_with_students(
    client, mentor_headers, cohort, student_user
):
    """Статистика с одним студентом."""
    client.post(
        f"/api/v1/cohorts/{cohort['id']}/members",
        json={"user_id": student_user["id"], "role": "student"},
        headers=mentor_headers,
    )

    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}/stats",
        headers=mentor_headers,
    )

    data = response.json()
    assert data["total_students"] == 1
    assert data["is_full"] is False


# ---------- RBAC ----------

def test_other_mentor_cannot_see_cohort(
    client, mentor_headers, cohort, db_session
):
    """Другой ментор не видит чужую когорту."""
    from app.crud.user import get_user_by_email
    from app.models.user import UserRole

    # Регистрируем второго ментора
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "mentor2@qahub.io",
            "username": "mentor2",
            "password": "mentor12345",
        },
    )

    user = get_user_by_email(db_session, "mentor2@qahub.io")
    if user:
        user.role = UserRole.MENTOR
        db_session.add(user)
        db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "mentor2@qahub.io", "password": "mentor12345"},
    )
    second_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Пытаемся получить чужую когорту
    response = client.get(
        f"/api/v1/cohorts/{cohort['id']}",
        headers=second_headers,
    )

    assert response.status_code == 403



# ---------- Уникальность имени когорты ----------

def test_create_cohort_duplicate_name(
    client, mentor_headers, cohort_data, cohort
):
    """Дубликат имени когорты у одного ментора — 409."""
    response = client.post(
        "/api/v1/cohorts",
        json=cohort_data,  # то же имя, что у cohort
        headers=mentor_headers,
    )

    assert response.status_code == 409
    assert "already have a cohort named" in response.json()["detail"]


def test_create_cohort_same_name_different_mentor(
    client, mentor_headers, cohort_data, cohort, db_session
):
    """Разные менторы могут иметь когорты с одинаковыми именами."""
    from app.crud.user import get_user_by_email
    from app.models.user import UserRole

    # Второй ментор
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "mentor2@qahub.io",
            "username": "mentor2",
            "password": "mentor12345",
        },
    )

    user2 = get_user_by_email(db_session, "mentor2@qahub.io")
    if user2:
        user2.role = UserRole.MENTOR
        db_session.add(user2)
        db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "mentor2@qahub.io", "password": "mentor12345"},
    )
    mentor2_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Второй ментор создаёт когорту с тем же именем — должно работать
    response = client.post(
        "/api/v1/cohorts",
        json=cohort_data,
        headers=mentor2_headers,
    )

    assert response.status_code == 201
