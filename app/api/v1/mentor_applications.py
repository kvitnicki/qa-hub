"""
Эндпоинты для MentorApplication.

Пользовательские:
- POST   /mentor-applications         — подать заявку (GUEST)
- GET    /mentor-applications/my      — мои заявки
- DELETE /mentor-applications/{id}    — отменить свою pending

Админские:
- GET    /admin/mentor-applications   — список всех заявок
- POST   /admin/mentor-applications/{id}/approve — одобрить
- POST   /admin/mentor-applications/{id}/reject  — отклонить
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models.mentor_application import ApplicationStatus
from app.schemas.mentor_application import (
    MentorApplicationCreate,
    MentorApplicationRead,
)
from app.services.mentor_application import (
    ApplicationAlreadyExistsError,
    ApplicationNotFoundError,
    InvalidApplicationStatusError,
    MentorApplicationError,
    NotAdminError,
    NotGuestError,
    approve_application,
    cancel_my_application,
    get_my_active_application,
    get_my_applications,
    list_applications,
    reject_application,
    submit_application,
)


router = APIRouter(tags=["mentor-applications"])


def _app_error_to_http(e: Exception) -> HTTPException:
    """Маппит доменные исключения заявок в HTTPException."""
    if isinstance(e, ApplicationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, (ApplicationAlreadyExistsError, InvalidApplicationStatusError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if isinstance(e, (NotGuestError, NotAdminError)):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if isinstance(e, MentorApplicationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------- Пользовательские ----------

@router.post(
    "/mentor-applications",
    response_model=MentorApplicationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Подать заявку на менторство",
    responses={
        403: {"description": "Только GUEST может подавать заявку"},
        409: {"description": "Уже есть активная заявка"},
    },
)
def submit_application_endpoint(
    data: MentorApplicationCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> MentorApplicationRead:
    """Подаёт заявку на роль ментора. Доступно только GUEST."""
    try:
        return submit_application(db, data, user=current_user)
    except Exception as e:
        raise _app_error_to_http(e)


@router.get(
    "/mentor-applications/my",
    response_model=list[MentorApplicationRead],
    summary="Мои заявки на менторство",
)
def list_my_applications(
    db: DbSession,
    current_user: CurrentUser,
) -> list[MentorApplicationRead]:
    """Возвращает все заявки текущего пользователя (история)."""
    return get_my_applications(db, user=current_user)


@router.get(
    "/mentor-applications/my/active",
    response_model=MentorApplicationRead | None,
    summary="Моя активная заявка",
)
def get_my_active_application_endpoint(
    db: DbSession,
    current_user: CurrentUser,
) -> MentorApplicationRead | None:
    """Возвращает активную (pending/in_review) заявку или None."""
    return get_my_active_application(db, user=current_user)


@router.delete(
    "/mentor-applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отменить свою заявку",
    responses={
        404: {"description": "Заявка не найдена"},
        409: {"description": "Заявка не в статусе pending"},
    },
)
def cancel_my_application_endpoint(
    application_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Отменяет свою pending-заявку."""
    try:
        cancel_my_application(db, application_id, user=current_user)
    except Exception as e:
        raise _app_error_to_http(e)
    return None


# ---------- Админские ----------

@router.get(
    "/admin/mentor-applications",
    response_model=list[MentorApplicationRead],
    summary="Список заявок (только ADMIN)",
    responses={403: {"description": "Только ADMIN"}},
)
def list_applications_endpoint(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: ApplicationStatus | None = Query(
        None,
        alias="status",
        description="Фильтр по статусу",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[MentorApplicationRead]:
    """Список всех заявок на менторство."""
    try:
        return list_applications(
            db,
            admin=current_user,
            status=status_filter,
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        raise _app_error_to_http(e)


@router.post(
    "/admin/mentor-applications/{application_id}/approve",
    response_model=MentorApplicationRead,
    summary="Одобрить заявку (только ADMIN)",
    responses={
        403: {"description": "Только ADMIN"},
        404: {"description": "Заявка не найдена"},
        409: {"description": "Заявка не в pending/in_review"},
    },
)
def approve_application_endpoint(
    application_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> MentorApplicationRead:
    """
    Одобряет заявку. Роль пользователя меняется на MENTOR.
    """
    try:
        return approve_application(db, application_id, admin=current_user)
    except Exception as e:
        raise _app_error_to_http(e)


@router.post(
    "/admin/mentor-applications/{application_id}/reject",
    response_model=MentorApplicationRead,
    summary="Отклонить заявку (только ADMIN)",
    responses={
        403: {"description": "Только ADMIN"},
        404: {"description": "Заявка не найдена"},
        409: {"description": "Заявка не в pending/in_review"},
    },
)
def reject_application_endpoint(
    application_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    rejection_reason: str | None = Query(
        None,
        max_length=2000,
        description="Причина отклонения",
    ),
) -> MentorApplicationRead:
    """Отклоняет заявку. Роль пользователя остаётся GUEST."""
    try:
        return reject_application(
            db,
            application_id,
            admin=current_user,
            rejection_reason=rejection_reason,
        )
    except Exception as e:
        raise _app_error_to_http(e)
