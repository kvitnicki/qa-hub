"""
Бизнес-логика для TestCase и TestStep.

Правила:
- Тест-кейс принадлежит проекту.
- suite_id должен принадлежать тому же проекту.
- Пользователь должен иметь доступ к проекту.
"""

import uuid

from sqlalchemy.orm import Session

from app.crud import test_case as case_crud
from app.crud import test_suite as suite_crud
from app.models.test_case import TestCase, TestStep
from app.models.user import User
from app.schemas.test_case import (
    TestCaseCreate,
    TestCaseUpdate,
    TestStepCreate,
)
from app.services.project import check_project_access


class CaseError(Exception):
    """Базовое исключение для тест-кейсов."""


class CaseNotFoundError(CaseError):
    """Тест-кейс не найден."""


class StepNotFoundError(CaseError):
    """Шаг не найден."""


class InvalidSuiteError(CaseError):
    """Сьют не принадлежит проекту."""


def _get_case_or_404(
    db: Session,
    case_id: uuid.UUID,
    project_id: uuid.UUID,
) -> TestCase:
    """Находит тест-кейс или бросает CaseNotFoundError."""
    case = case_crud.get_case_by_id(db, case_id)
    if case is None or case.project_id != project_id:
        raise CaseNotFoundError(f"TestCase {case_id} not found in project {project_id}")
    return case


def _validate_suite(
    db: Session,
    suite_id: uuid.UUID | None,
    project_id: uuid.UUID,
) -> None:
    """
    Проверяет, что сьют существует и принадлежит проекту.

    Если suite_id=None — ничего не проверяем.
    """
    if suite_id is None:
        return

    suite = suite_crud.get_suite_by_id(db, suite_id)
    if suite is None or suite.project_id != project_id:
        raise InvalidSuiteError(f"Suite {suite_id} not found in project {project_id}")


def create_case(
    db: Session,
    project_id: uuid.UUID,
    data: TestCaseCreate,
    user: User,
) -> TestCase:
    """
    Создаёт тест-кейс с проверками:
    - доступ к проекту;
    - suite_id (если указан) в том же проекте.
    """
    check_project_access(db, project_id, user)
    _validate_suite(db, data.suite_id, project_id)

    return case_crud.create_case(db, project_id, data, created_by=user.id)


def update_case(
    db: Session,
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: TestCaseUpdate,
    user: User,
) -> TestCase:
    """Обновляет тест-кейс с проверками."""
    check_project_access(db, project_id, user)
    case = _get_case_or_404(db, case_id, project_id)

    if data.suite_id is not None:
        _validate_suite(db, data.suite_id, project_id)

    return case_crud.update_case(db, case, data)


def delete_case(
    db: Session,
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    user: User,
) -> None:
    """Удаляет тест-кейс. Шаги удалятся каскадно."""
    check_project_access(db, project_id, user)
    case = _get_case_or_404(db, case_id, project_id)
    case_crud.delete_case(db, case)


# ---------- Шаги ----------

def add_step_to_case(
    db: Session,
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: TestStepCreate,
    user: User,
) -> TestStep:
    """
    Добавляет шаг к тест-кейсу.

    Если order не задан — ставим в конец (max(order) + 1).
    """
    check_project_access(db, project_id, user)
    case = _get_case_or_404(db, case_id, project_id)

    # Определяем order
    if data.order is not None:
        order = data.order
    else:
        existing_steps = case_crud.get_steps_by_case(db, case.id)
        order = max((s.order for s in existing_steps), default=0) + 1

    return case_crud.add_step(
        db,
        case_id=case.id,
        order=order,
        action=data.action,
        expected_result=data.expected_result,
        data=data.data,
    )


def delete_step_from_case(
    db: Session,
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    step_id: uuid.UUID,
    user: User,
) -> None:
    """Удаляет шаг из тест-кейса."""
    check_project_access(db, project_id, user)
    case = _get_case_or_404(db, case_id, project_id)

    step = case_crud.get_step_by_id(db, step_id)
    if step is None or step.test_case_id != case.id:
        raise StepNotFoundError(f"Step {step_id} not found in case {case_id}")

    case_crud.delete_step(db, step)
