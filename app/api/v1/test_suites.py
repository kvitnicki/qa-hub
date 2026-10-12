"""
Эндпоинты для TestSuite.

Сьюты вложены в проект: /projects/{project_id}/suites/*
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.crud import test_suite as suite_crud
from app.schemas.test_suite import (
    TestSuiteCreate,
    TestSuiteRead,
    TestSuiteTree,
    TestSuiteUpdate,
)
from app.services.project import (
    ProjectNotFoundError,
    check_project_access,
)
from app.services.test_suite import (
    SuiteError,
    SuiteNotFoundError,
    create_suite,
    delete_suite,
    update_suite,
)


router = APIRouter(
    prefix="/projects/{project_id}/suites",
    tags=["test-suites"],
)


def _suite_error_to_http(e: Exception) -> HTTPException:
    """Маппит доменные исключения сьютов в HTTPException."""
    if isinstance(e, SuiteNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, SuiteError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------- Список ----------

@router.get(
    "",
    response_model=list[TestSuiteRead],
    summary="Список сьютов проекта",
)
def list_suites(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    only_roots: bool = Query(False, description="Только корневые сьюты"),
    parent_id: uuid.UUID | None = Query(None, description="Только дети сьюта"),
) -> list[TestSuiteRead]:
    """
    Список сьютов проекта (плоский).

    Параметры:
    - only_roots=true — только корневые сьюты (parent_id IS NULL).
    - parent_id=UUID — только дети конкретного сьюта.
    """
    try:
        check_project_access(db, project_id, current_user)
    except Exception as e:
        raise _suite_error_to_http(e)

    return suite_crud.get_suites_by_project(
        db,
        project_id=project_id,
        parent_id=parent_id,
        only_roots=only_roots,
    )


# ---------- Создание ----------

@router.post(
    "",
    response_model=TestSuiteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать сьют",
)
def create_suite_endpoint(
    project_id: uuid.UUID,
    data: TestSuiteCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestSuiteRead:
    """Создаёт сьют в проекте."""
    try:
        return create_suite(db, project_id, data, user=current_user)
    except Exception as e:
        raise _suite_error_to_http(e)


# ---------- Дерево ----------

@router.get(
    "/tree",
    response_model=list[TestSuiteTree],
    summary="Дерево сьютов проекта",
)
def get_suite_tree(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[TestSuiteTree]:
    """
    Возвращает дерево сьютов проекта.

    Корневые сьюты с вложенными детьми (рекурсивно).
    """
    try:
        check_project_access(db, project_id, current_user)
    except Exception as e:
        raise _suite_error_to_http(e)

    all_suites = suite_crud.get_suites_by_project(db, project_id)

    trees: dict[uuid.UUID, TestSuiteTree] = {
        s.id: TestSuiteTree(
            id=s.id,
            project_id=s.project_id,
            parent_id=s.parent_id,
            name=s.name,
            description=s.description,
            order=s.order,
            created_by=s.created_by,
            created_at=s.created_at,
            updated_at=s.updated_at,
            children=[],
        )
        for s in all_suites
    }

    roots: list[TestSuiteTree] = []

    for s in all_suites:
        node = trees[s.id]
        if s.parent_id is None:
            roots.append(node)
        else:
            parent = trees.get(s.parent_id)
            if parent is not None:
                parent.children.append(node)

    return roots


# ---------- Получить один ----------

@router.get(
    "/{suite_id}",
    response_model=TestSuiteRead,
    summary="Получить сьют",
)
def get_suite(
    project_id: uuid.UUID,
    suite_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> TestSuiteRead:
    """Возвращает сьют по id."""
    try:
        check_project_access(db, project_id, current_user)
    except Exception as e:
        raise _suite_error_to_http(e)

    suite = suite_crud.get_suite_by_id(db, suite_id)
    if suite is None or suite.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite {suite_id} not found",
        )
    return suite


# ---------- Обновление ----------

@router.patch(
    "/{suite_id}",
    response_model=TestSuiteRead,
    summary="Обновить сьют",
)
def update_suite_endpoint(
    project_id: uuid.UUID,
    suite_id: uuid.UUID,
    data: TestSuiteUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestSuiteRead:
    """Обновляет сьют."""
    try:
        return update_suite(db, project_id, suite_id, data, user=current_user)
    except Exception as e:
        raise _suite_error_to_http(e)


# ---------- Удаление ----------

@router.delete(
    "/{suite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить сьют",
)
def delete_suite_endpoint(
    project_id: uuid.UUID,
    suite_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет сьют и всех его детей каскадно."""
    try:
        delete_suite(db, project_id, suite_id, user=current_user)
    except Exception as e:
        raise _suite_error_to_http(e)
    return None
