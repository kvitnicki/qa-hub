# qa-hub

[![CI](https://github.com/kvitnicki/qa-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/kvitnicki/qa-hub/actions/workflows/ci.yml)
[![CD](https://github.com/kvitnicki/qa-hub/actions/workflows/cd.yml/badge.svg)](https://github.com/kvitnicki/qa-hub/actions/workflows/cd.yml)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Tests](https://img.shields.io/badge/tests-185%20passed-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

> **Test Case Management System** — open-source платформа для управления тест-кейсами, сьютами, прогонами и результатами.

---

## О проекте

`qa-hub` — backend-платформа для QA-команд:

- Организация тест-кейсов в проекты и сьюты.
- Управление ролями участников (RBAC).
- JWT-аутентификация (access + refresh).
- Прогоны тестов и результаты (в разработке).
- Аудит изменений (в разработке).

---

## Технологии

- **Python 3.12**, **FastAPI 0.115**
- **SQLAlchemy 2.0** (sync), **PostgreSQL 16**, **Alembic**
- **JWT** (python-jose), **bcrypt** (passlib)
- **Pydantic v2**
- **pytest**, **httpx**
- **ruff** (linter)
- **Docker**, **docker-compose**
- **GitHub Actions** (CI)

---

## Архитектура

Слоистая архитектура:

- **API** (`app/api/`) — HTTP-запросы, валидация, маппинг ошибок.
- **Services** (`app/services/`) — бизнес-логика, RBAC, правила.
- **CRUD** (`app/crud/`) — SQL-операции.
- **Models** (`app/models/`) — SQLAlchemy-модели.

**API** знает только о схемах и сервисах. **Services** — о бизнес-правилах. **CRUD** — о БД. **Models** — о структуре.

---

## Структура

    qa-hub/
    ├── app/
    │   ├── api/         # HTTP-эндпоинты
    │   ├── core/        # config, database, security
    │   ├── models/      # SQLAlchemy-модели
    │   ├── schemas/     # Pydantic-схемы
    │   ├── crud/        # SQL-операции
    │   ├── services/    # бизнес-логика
    │   └── main.py
    ├── alembic/         # миграции
    ├── tests/           # pytest
    ├── .github/workflows/ci.yml
    ├── Dockerfile
    ├── docker-compose.yml
    └── README.md

---
---

## 🌐 Live Demo

Проект развёрнут на VPS и автоматически обновляется через CD.

- **API:** http://185.149.144.127:8000
- **Swagger UI:** http://185.149.144.127:8000/docs
- **ReDoc:** http://185.149.144.127:8000/redoc

**Демо-аккаунты:**

| Роль | Email | Пароль |
|------|-------|--------|
| Admin | `admin@qahub.io` | `admin12345` |
| Mentor | `mentor_test@qahub.io` | `mentor12345` |
| Student | `new-student@qahub.io` | `newstudent12345` |

---

## 🚀 Как это работает

**CI/CD Pipeline:**

**Технологии инфраструктуры:**
- **VPS:** Ubuntu 24.04
- **Docker:** multi-stage builds, non-root user
- **PostgreSQL 16:** в отдельном контейнере
- **Nginx:** (позже) reverse proxy + HTTPS
- **GitHub Actions:** CI + CD
- **GHCR:** GitHub Container Registry
## Быстрый старт

### Требования

- Docker и docker-compose
- Python 3.12+
- Git

### 1. Клонировать репозиторий

    git clone git@github.com:kvitnicki/qa-hub.git
    cd qa-hub

### 2. Запустить PostgreSQL

    docker run -d --name qa-hub-db \
      -e POSTGRES_USER=qahub \
      -e POSTGRES_PASSWORD=qahub_secret \
      -e POSTGRES_DB=qahub \
      -p 5432:5432 \
      postgres:16-alpine

### 3. Установить зависимости

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

### 4. Применить миграции

    alembic upgrade head

### 5. Запустить приложение

    uvicorn app.main:app --reload

Swagger: http://localhost:8000/docs

---

## Тесты

Запустить все тесты:

    pytest -v

Ожидаемо: **46 passed**.

Покрытие:

- `test_auth.py` — 16 тестов (регистрация, логин, refresh, /me).
- `test_projects.py` — 18 тестов (CRUD, архивация, RBAC).
- `test_members.py` — 12 тестов (участники, защита owner'а).

---

## API Endpoints

### Auth

| Метод | Путь | Auth |
|-------|------|------|
| POST | `/api/v1/auth/register` | нет |
| POST | `/api/v1/auth/login` | нет |
| POST | `/api/v1/auth/refresh` | нет |
| GET | `/api/v1/auth/me` | да |

### Projects

| Метод | Путь | Auth |
|-------|------|------|
| GET | `/api/v1/projects` | да |
| POST | `/api/v1/projects` | да |
| GET | `/api/v1/projects/{id}` | да |
| PATCH | `/api/v1/projects/{id}` | owner/admin |
| DELETE | `/api/v1/projects/{id}` | owner/admin |
| POST | `/api/v1/projects/{id}/archive` | owner/admin |

### Members

| Метод | Путь | Auth |
|-------|------|------|
| GET | `/api/v1/projects/{id}/members` | да |
| POST | `/api/v1/projects/{id}/members` | owner/admin |
| PATCH | `/api/v1/projects/{id}/members/{member_id}` | owner/admin |
| DELETE | `/api/v1/projects/{id}/members/{member_id}` | owner/admin |

---

## Пример запроса

Регистрация:

    curl -X POST http://localhost:8000/api/v1/auth/register \
      -H "Content-Type: application/json" \
      -d '{"email":"user@example.com","username":"john","password":"SecurePass123"}'

Логин:

    curl -X POST http://localhost:8000/api/v1/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email":"user@example.com","password":"SecurePass123"}'

Создать проект:

    curl -X POST http://localhost:8000/api/v1/projects \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"name":"Mobile Tests","key":"MOBILE","description":"Tests for mobile"}'

---

## Roadmap

### Готово

- [x] JWT-аутентификация (access + refresh)
- [x] Роли пользователей (admin/qa_lead/tester/viewer)
- [x] Проекты (CRUD + архивация)
- [x] Участники проектов (M:N с ролями)
- [x] RBAC на уровне проектов
- [x] 46 интеграционных тестов
- [x] CI: lint + test + build
- [x] Docker (multi-stage, non-root)

### В разработке

- [ ] TestSuite — дерево сьютов
- [ ] TestCase + TestStep
- [ ] TestRun + TestResult
- [ ] AuditLog
- [ ] Метрики (pass rate, flaky)

### Планы

- [ ] CD (деплой на VPS через GHCR)
- [ ] Postman-коллекция + Newman
- [ ] Allure-отчёты
- [ ] Redis (кеш + rate limiting)
- [ ] Celery (фоновые задачи)
- [ ] WebSocket (live-обновления)
- [ ] Frontend

---

## Лицензия

MIT License.

---

## Автор

**kvitnicki** — [github.com/kvitnicki](https://github.com/kvitnicki)
