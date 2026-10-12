"""
Бизнес-логика для TestSuite.

Правила:
- Сьют принадлежит проекту.
- parent_id должен принадлежать тому же проекту.
- Пользователь должен иметь доступ к проекту.
"""

import uuid

from sqlalchemy.orm import Session

from app.crud import test_suite as suite_crud
from app.models.test_suite import TestSuite
from app.models.user import User
from app.schemas.test_suite import TestSuiteCreate, TestSuiteUpdate
from app.services.project import (
    check_project_access,
)


class SuiteError(Exception):
    """Базовое исключение для сьютов."""


class SuiteNotFoundError(SuiteError):
    """Сьют не найден."""


class InvalidParentSuiteError(SuiteError):
    """Parent сьют не принадлежит этому проекту."""


def _get_suite_or_404(
    db: Session,
    suite_id: uuid.UUID,
    project_id: uuid.UUID,
) -> TestSuite:
    """Находит сьют или бросает SuiteNotFoundError."""
    suite = suite_crud.get_suite_by_id(db, suite_id)
    if suite is None or suite.project_id != project_id:
        raise SuiteNotFoundError(f"Suite {suite_id} not found in project {project_id}")
    return suite


def create_suite(
    db: Session,
    project_id: uuid.UUID,
    data: TestSuiteCreate,
    user: User,
) -> TestSuite:
    """
    Создаёт сьют с проверками:
    - проект существует и доступен пользователю;
    - если указан parent_id — сьют существует и в том же проекте.
    """
    check_project_access(db, project_id, user)

    if data.parent_id is not None:
        _get_suite_or_404(db, data.parent_id, project_id)

    return suite_crud.create_suite(db, project_id, data, created_by=user.id)


def update_suite(
    db: Session,
    project_id: uuid.UUID,
    suite_id: uuid.UUID,
    data: TestSuiteUpdate,
    user: User,
) -> TestSuite:
    """Обновляет сьют с проверками."""
    check_project_access(db, project_id, user)
    suite = _get_suite_or_404(db, suite_id, project_id)

    # Если меняется parent_id — проверим, что он валиден
    if data.parent_id is not None:
        _get_suite_or_404(db, data.parent_id, project_id)

    return suite_crud.update_suite(db, suite, data)


def delete_suite(
    db: Session,
    project_id: uuid.UUID,
    suite_id: uuid.UUID,
    user: User,
) -> None:
    """Удаляет сьют. Дети удалятся каскадно."""
    check_project_access(db, project_id, user)
    suite = _get_suite_or_404(db, suite_id, project_id)
    suite_crud.delete_suite(db, suite)
