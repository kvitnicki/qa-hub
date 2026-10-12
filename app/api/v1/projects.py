"""
Эндпоинты для проектов и участников.

Все требуют аутентификации. Часть операций — только для owner/admin.
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.crud import project as project_crud
from app.schemas.project import (
    ProjectCreate,
    ProjectMemberAdd,
    ProjectMemberRead,
    ProjectMemberUpdate,
    ProjectRead,
    ProjectReadWithMembers,
    ProjectUpdate,
)
from app.services.project import (
    CannotRemoveOwnerError,
    MemberAlreadyExistsError,
    MemberNotFoundError,
    NotProjectOwnerError,
    ProjectKeyAlreadyExistsError,
    ProjectNotFoundError,
    UserNotFoundError,
    add_member,
    archive_project,
    check_project_access,
    create_project,
    delete_project,
    remove_member,
    update_member_role,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_error_to_http(e: Exception) -> HTTPException:
    """
    Мапит доменные исключения проектов в HTTPException.

    Единая точка перевода ошибок — не дублировать try/except в каждом эндпоинте.
    """
    if isinstance(e, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, ProjectKeyAlreadyExistsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if isinstance(e, MemberAlreadyExistsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if isinstance(e, (NotProjectOwnerError, CannotRemoveOwnerError)):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if isinstance(e, (MemberNotFoundError, UserNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # Любое другое — 400
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------- Проекты ----------

@router.get(
    "",
    response_model=list[ProjectRead],
    summary="Список проектов",
)
def list_projects(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0, description="Сколько пропустить"),
    limit: int = Query(50, ge=1, le=200, description="Сколько вернуть"),
    include_archived: bool = Query(False, description="Включать архивные"),
) -> list[ProjectRead]:
    """
    Возвращает список проектов.

    Пока без разграничения по правам — просто все проекты.
    В будущем: только те, где текущий user — участник или admin.
    """
    return project_crud.get_projects(
        db,
        skip=skip,
        limit=limit,
        include_archived=include_archived,
    )


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать проект",
    responses={409: {"description": "Key уже занят"}},
)
def create_project_endpoint(
    data: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectRead:
    """Создаёт проект. Текущий пользователь становится владельцем."""
    try:
        return create_project(db, data, owner=current_user)
    except Exception as e:
        raise _project_error_to_http(e)


@router.get(
    "/{project_id}",
    response_model=ProjectReadWithMembers,
    summary="Получить проект с участниками",
    responses={404: {"description": "Проект не найден"}},
)
def get_project(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectReadWithMembers:
    """Возвращает проект со всеми участниками. Доступ — участникам и admin."""
    try:
        project = check_project_access(db, project_id, current_user)
    except Exception as e:
        raise _project_error_to_http(e)

    # Загружаем members вручную, чтобы точно были в ответе
    project.members = project_crud.get_members(db, project.id)
    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    summary="Обновить проект",
    responses={
        403: {"description": "Не owner/admin"},
        404: {"description": "Проект не найден"},
    },
)
def update_project_endpoint(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectRead:
    """Обновляет проект. Только owner или admin."""
    try:
        return update_project(db, project_id, data, user=current_user)
    except Exception as e:
        raise _project_error_to_http(e)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить проект",
    responses={
        403: {"description": "Не owner/admin"},
        404: {"description": "Проект не найден"},
    },
)
def delete_project_endpoint(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет проект со всеми участниками."""
    try:
        delete_project(db, project_id, user=current_user)
    except Exception as e:
        raise _project_error_to_http(e)
    return None


@router.post(
    "/{project_id}/archive",
    response_model=ProjectRead,
    summary="Архивировать проект",
    responses={
        403: {"description": "Не owner/admin"},
        404: {"description": "Проект не найден"},
    },
)
def archive_project_endpoint(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectRead:
    """Архивирует проект (soft delete)."""
    try:
        return archive_project(db, project_id, user=current_user)
    except Exception as e:
        raise _project_error_to_http(e)


# ---------- Участники ----------

@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberRead],
    summary="Список участников проекта",
    responses={404: {"description": "Проект не найден"}},
)
def list_members(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ProjectMemberRead]:
    """Участники проекта. Доступ — участникам и admin."""
    try:
        check_project_access(db, project_id, current_user)
    except Exception as e:
        raise _project_error_to_http(e)

    return project_crud.get_members(db, project_id)


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить участника",
    responses={
        403: {"description": "Не owner/admin"},
        404: {"description": "Проект или пользователь не найден"},
        409: {"description": "Пользователь уже в проекте"},
    },
)
def add_member_endpoint(
    project_id: uuid.UUID,
    data: ProjectMemberAdd,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectMemberRead:
    """Добавляет участника. Только owner/admin."""
    try:
        return add_member(db, project_id, data, user=current_user)
    except Exception as e:
        raise _project_error_to_http(e)


@router.patch(
    "/{project_id}/members/{member_id}",
    response_model=ProjectMemberRead,
    summary="Изменить роль участника",
    responses={
        403: {"description": "Не owner/admin"},
        404: {"description": "Проект или участник не найден"},
    },
)
def update_member_endpoint(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    data: ProjectMemberUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectMemberRead:
    """Меняет роль участника. Только owner/admin."""
    try:
        return update_member_role(db, project_id, member_id, data, user=current_user)
    except Exception as e:
        raise _project_error_to_http(e)


@router.delete(
    "/{project_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить участника",
    responses={
        403: {"description": "Не owner/admin или попытка удалить owner"},
        404: {"description": "Участник не найден"},
    },
)
def remove_member_endpoint(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет участника. Owner удалить нельзя."""
    try:
        remove_member(db, project_id, member_id, user=current_user)
    except Exception as e:
        raise _project_error_to_http(e)
    return None
