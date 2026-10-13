"""
Тесты для TestRun и TestResult API.
"""

# ---------- Создание ----------

def test_create_run_success(client, auth_headers, project, run_data):
    """Успешное создание прогона."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json=run_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == run_data["name"]
    assert data["environment"] == "staging"
    assert data["status"] == "in_progress"
    assert data["finished_at"] is None


def test_create_run_no_cases(client, auth_headers, project):
    """Прогон без кейсов — создаётся пустым."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"name": "Empty run", "test_case_ids": []},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["status"] == "in_progress"


def test_create_run_invalid_case(client, auth_headers, project):
    """Невалидный test_case_id — 400."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"name": "Bad run", "test_case_ids": [fake_id]},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_create_run_case_from_other_project(
    client, auth_headers, project, second_user
):
    """Кейс из чужого проекта — 400."""
    second_project = client.post(
        "/api/v1/projects",
        json={"name": "Second", "key": "SEC"},
        headers=auth_headers,
    ).json()

    case = client.post(
        f"/api/v1/projects/{project['id']}/cases",
        json={"title": "Cross project case"},
        headers=auth_headers,
    ).json()

    response = client.post(
        f"/api/v1/projects/{second_project['id']}/runs",
        json={"name": "Cross run", "test_case_ids": [case["id"]]},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_create_run_without_auth(client, project, run_data):
    """Без токена — 401."""
    response = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json=run_data,
    )

    assert response.status_code == 401


# ---------- Список ----------

def test_list_runs_empty(client, auth_headers, project):
    """Пустой список прогонов."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/runs",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_runs(client, auth_headers, project, run):
    """Список содержит созданный прогон."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/runs",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == run["id"]


# ---------- Получение ----------

def test_get_run_with_results(client, auth_headers, project, run_with_results):
    """Прогон с двумя результатами."""
    assert len(run_with_results["results"]) == 2
    for r in run_with_results["results"]:
        assert r["status"] == "in_progress"
        assert r["test_run_id"] == run_with_results["id"]


def test_get_run_not_found(client, auth_headers, project):
    """Несуществующий прогон — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(
        f"/api/v1/projects/{project['id']}/runs/{fake_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


# ---------- Обновление прогона ----------

def test_update_run_name(client, auth_headers, project, run):
    """PATCH имени прогона."""
    response = client.patch(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}",
        json={"name": "Renamed run"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed run"


def test_update_run_complete(client, auth_headers, project, run):
    """PATCH статуса на completed — устанавливается finished_at."""
    response = client.patch(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}",
        json={"status": "completed"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["finished_at"] is not None


# ---------- Обновление результата ----------

def test_update_result_passed(client, auth_headers, project, run_with_results):
    """Обновление результата на passed."""
    result = run_with_results["results"][0]

    response = client.patch(
        f"/api/v1/projects/{project['id']}/runs/{run_with_results['id']}/results/{result['id']}",
        json={"status": "passed", "duration_ms": 1500, "comment": "OK"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "passed"
    assert data["duration_ms"] == 1500
    assert data["comment"] == "OK"


def test_update_result_with_attachments(client, auth_headers, project, run_with_results):
    """Обновление результата с attachments (JSONB)."""
    result = run_with_results["results"][0]

    response = client.patch(
        f"/api/v1/projects/{project['id']}/runs/{run_with_results['id']}/results/{result['id']}",
        json={
            "status": "failed",
            "attachments": {
                "screenshot": "https://example.com/s.png",
                "log": "https://example.com/log.txt",
            },
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["attachments"]["screenshot"] == "https://example.com/s.png"
    assert data["attachments"]["log"] == "https://example.com/log.txt"


def test_update_result_invalid_status(client, auth_headers, project, run_with_results):
    """Невалидный статус — 422."""
    result = run_with_results["results"][0]

    response = client.patch(
        f"/api/v1/projects/{project['id']}/runs/{run_with_results['id']}/results/{result['id']}",
        json={"status": "wrong_status"},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_update_result_not_found(client, auth_headers, project, run):
    """Несуществующий результат — 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.patch(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}/results/{fake_id}",
        json={"status": "passed"},
        headers=auth_headers,
    )

    assert response.status_code == 404


# ---------- Автозавершение ----------

def test_run_auto_completes(client, auth_headers, project, completed_run):
    """После обновления всех результатов прогон становится completed."""
    assert completed_run["status"] == "completed"
    assert completed_run["finished_at"] is not None


def test_run_stays_in_progress_with_one_result(
    client, auth_headers, project, run_with_results
):
    """Если хотя бы один результат in_progress — прогон остаётся in_progress."""
    run_id = run_with_results["id"]
    results = run_with_results["results"]

    client.patch(
        f"/api/v1/projects/{project['id']}/runs/{run_id}/results/{results[0]['id']}",
        json={"status": "passed"},
        headers=auth_headers,
    )

    response = client.get(
        f"/api/v1/projects/{project['id']}/runs/{run_id}",
        headers=auth_headers,
    )
    assert response.json()["status"] == "in_progress"


# ---------- Статистика ----------

def test_run_stats_all_passed(client, auth_headers, project, run_with_results):
    """Все passed — pass_rate 100%."""
    run_id = run_with_results["id"]
    results = run_with_results["results"]

    for r in results:
        client.patch(
            f"/api/v1/projects/{project['id']}/runs/{run_id}/results/{r['id']}",
            json={"status": "passed"},
            headers=auth_headers,
        )

    response = client.get(
        f"/api/v1/projects/{project['id']}/runs/{run_id}/stats",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["passed"] == 2
    assert data["failed"] == 0
    assert data["pass_rate"] == 100.0


def test_run_stats_half_passed(client, auth_headers, project, completed_run):
    """1 passed, 1 failed — pass_rate 50%."""
    response = client.get(
        f"/api/v1/projects/{project['id']}/runs/{completed_run['id']}/stats",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["passed"] == 1
    assert data["failed"] == 1
    assert data["pass_rate"] == 50.0


def test_run_stats_empty(client, auth_headers, project):
    """Прогон без кейсов — pass_rate 0."""
    run = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"name": "Empty", "test_case_ids": []},
        headers=auth_headers,
    ).json()

    response = client.get(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}/stats",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["pass_rate"] == 0.0


# ---------- Удаление ----------

def test_delete_run(client, auth_headers, project, run):
    """Удаление прогона."""
    response = client.delete(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    response = client.get(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------- RBAC ----------

def test_other_user_cannot_access_runs(
    client, auth_headers, project, second_user, run
):
    """Другой пользователь не видит прогоны чужого проекта."""
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "second@qahub.io", "password": "secondpass12345"},
    )
    second_token = login.json()["access_token"]
    second_headers = {"Authorization": f"Bearer {second_token}"}

    response = client.get(
        f"/api/v1/projects/{project['id']}/runs",
        headers=second_headers,
    )
    assert response.status_code == 404

    response = client.get(
        f"/api/v1/projects/{project['id']}/runs/{run['id']}",
        headers=second_headers,
    )
    assert response.status_code == 404
