"""
Эндпоинты для TestCase и TestStep.

Тест-кейсы вложены в проект: /projects/{project_id}/cases/*
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.crud import test_case as case_crud
from app.schemas.test_case import (
    TestCaseCreate,
    TestCaseRead,
    TestCaseUpdate,
    TestStepCreate,
    TestStepRead,
)
from app.services.project import (
    ProjectNotFoundError,
    check_project_access,
)
from app.services.test_case import (
    CaseError,
    CaseNotFoundError,
    InvalidSuiteError,
    StepNotFoundError,
    add_step_to_case,
    create_case,
    delete_case,
    delete_step_from_case,
    update_case,
)


router = APIRouter(
    prefix="/projects/{project_id}/cases",
    tags=["test-cases"],
)


def _case_error_to_http(e: Exception) -> HTTPException:
    """Маппит доменные исключения тест-кейсов в HTTPException."""
    if isinstance(e, (CaseNotFoundError, StepNotFoundError, ProjectNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, (InvalidSuiteError, CaseError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "",
    response_model=list[TestCaseRead],
    summary="Список тест-кейсов проекта",
)
def list_cases(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    suite_id: uuid.UUID | None = Query(None, description="Фильтр по сьюту"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[TestCaseRead]:
    """Список тест-кейсов проекта (опционально — по сьюту)."""
    try:
        check_project_access(db, project_id, current_user)
    except Exception as e:
        raise _case_error_to_http(e)

    return case_crud.get_cases_by_project(
        db,
        project_id=project_id,
        suite_id=suite_id,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=TestCaseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать тест-кейс",
)
def create_case_endpoint(
    project_id: uuid.UUID,
    data: TestCaseCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestCaseRead:
    """Создаёт тест-кейс со шагами (шаги опциональны)."""
    try:
        return create_case(db, project_id, data, user=current_user)
    except Exception as e:
        raise _case_error_to_http(e)


@router.get(
    "/{case_id}",
    response_model=TestCaseRead,
    summary="Получить тест-кейс",
)
def get_case(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> TestCaseRead:
    """Возвращает тест-кейс со всеми шагами."""
    try:
        check_project_access(db, project_id, current_user)
    except Exception as e:
        raise _case_error_to_http(e)

    case = case_crud.get_case_by_id(db, case_id)
    if case is None or case.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TestCase {case_id} not found",
        )
    return case


@router.patch(
    "/{case_id}",
    response_model=TestCaseRead,
    summary="Обновить тест-кейс",
)
def update_case_endpoint(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: TestCaseUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestCaseRead:
    """Обновляет тест-кейс."""
    try:
        return update_case(db, project_id, case_id, data, user=current_user)
    except Exception as e:
        raise _case_error_to_http(e)


@router.delete(
    "/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить тест-кейс",
)
def delete_case_endpoint(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет тест-кейс и все его шаги."""
    try:
        delete_case(db, project_id, case_id, user=current_user)
    except Exception as e:
        raise _case_error_to_http(e)
    return None


# ---------- Шаги ----------

@router.post(
    "/{case_id}/steps",
    response_model=TestStepRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить шаг к тест-кейсу",
)
def add_step(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    data: TestStepCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestStepRead:
    """
    Добавляет шаг к тест-кейсу.

    Если order не задан — шаг ставится в конец.
    """
    try:
        return add_step_to_case(db, project_id, case_id, data, user=current_user)
    except Exception as e:
        raise _case_error_to_http(e)


@router.delete(
    "/{case_id}/steps/{step_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить шаг",
)
def delete_step(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    step_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет шаг из тест-кейса."""
    try:
        delete_step_from_case(db, project_id, case_id, step_id, user=current_user)
    except Exception as e:
        raise _case_error_to_http(e)
    return None
