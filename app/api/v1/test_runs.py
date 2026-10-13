"""
Эндпоинты для TestRun и TestResult.

Прогоны вложены в проект: /projects/{project_id}/runs/*
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.crud import test_run as run_crud
from app.schemas.test_run import (
    TestResultRead,
    TestResultUpdate,
    TestRunCreate,
    TestRunRead,
    TestRunReadWithResults,
    TestRunStats,
    TestRunUpdate,
)
from app.services.project import (
    ProjectNotFoundError,
    check_project_access,
)
from app.services.test_run import (
    InvalidTestCaseError,
    ResultNotFoundError,
    RunError,
    RunNotFoundError,
    create_run,
    delete_run,
    get_run_stats,
    update_result_status,
    update_run,
)


router = APIRouter(
    prefix="/projects/{project_id}/runs",
    tags=["test-runs"],
)


def _run_error_to_http(e: Exception) -> HTTPException:
    """Маппит доменные исключения прогонов в HTTPException."""
    if isinstance(e, (RunNotFoundError, ResultNotFoundError, ProjectNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, (InvalidTestCaseError, RunError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "",
    response_model=list[TestRunRead],
    summary="Список прогонов проекта",
)
def list_runs(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[TestRunRead]:
    """Список прогонов проекта (свежие сверху)."""
    try:
        check_project_access(db, project_id, current_user)
    except Exception as e:
        raise _run_error_to_http(e)

    return run_crud.get_runs_by_project(db, project_id, skip=skip, limit=limit)


@router.post(
    "",
    response_model=TestRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать прогон",
)
def create_run_endpoint(
    project_id: uuid.UUID,
    data: TestRunCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestRunRead:
    """Создаёт прогон и по TestResult на каждый test_case_id."""
    try:
        return create_run(db, project_id, data, user=current_user)
    except Exception as e:
        raise _run_error_to_http(e)


@router.get(
    "/{run_id}",
    response_model=TestRunReadWithResults,
    summary="Получить прогон с результатами",
)
def get_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> TestRunReadWithResults:
    """Возвращает прогон со всеми результатами."""
    try:
        check_project_access(db, project_id, current_user)
    except Exception as e:
        raise _run_error_to_http(e)

    run = run_crud.get_run_by_id(db, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TestRun {run_id} not found",
        )

    # Явно загружаем результаты, чтобы они точно попали в ответ
    run.results = run_crud.get_results_by_run(db, run.id)
    return run


@router.patch(
    "/{run_id}",
    response_model=TestRunRead,
    summary="Обновить прогон",
)
def update_run_endpoint(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    data: TestRunUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestRunRead:
    """Обновляет прогон."""
    try:
        return update_run(db, project_id, run_id, data, user=current_user)
    except Exception as e:
        raise _run_error_to_http(e)


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить прогон",
)
def delete_run_endpoint(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет прогон. Результаты удалятся каскадно."""
    try:
        delete_run(db, project_id, run_id, user=current_user)
    except Exception as e:
        raise _run_error_to_http(e)
    return None


@router.get(
    "/{run_id}/stats",
    response_model=TestRunStats,
    summary="Статистика прогона",
)
def get_run_stats_endpoint(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> TestRunStats:
    """Возвращает статистику прогона."""
    try:
        return get_run_stats(db, project_id, run_id, user=current_user)
    except Exception as e:
        raise _run_error_to_http(e)


@router.patch(
    "/{run_id}/results/{result_id}",
    response_model=TestResultRead,
    summary="Обновить результат тест-кейса",
)
def update_result_endpoint(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    result_id: uuid.UUID,
    data: TestResultUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestResultRead:
    """
    Обновляет результат тест-кейса в прогоне.

    Если все результаты перестали быть in_progress — прогон автоматически
    завершается (status = completed, finished_at = now()).
    """
    try:
        return update_result_status(
            db,
            project_id=project_id,
            run_id=run_id,
            result_id=result_id,
            status=data.status,
            duration_ms=data.duration_ms,
            comment=data.comment,
            attachments=data.attachments,
            user=current_user,
        )
    except Exception as e:
        raise _run_error_to_http(e)
