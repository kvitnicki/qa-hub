"""
Эндпоинты для Invitation.

Ментор:
- POST   /cohorts/{cohort_id}/invitations        — отправить
- GET    /cohorts/{cohort_id}/invitations        — список когорты
- DELETE /invitations/{id}                        — отозвать

Пользователь:
- GET    /my/invitations                          — мои приглашения
- GET    /invitations/info/{token}                — публичная информация
- POST   /invitations/accept/{token}              — принять
- POST   /invitations/decline/{token}             — отклонить
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models.invitation import InvitationStatus
from app.schemas.invitation import (
    InvitationAcceptResponse,
    InvitationCreate,
    InvitationPublicInfo,
    InvitationRead,
)
from app.services.cohort import (
    CohortNotFoundError,
    NotCohortOwnerError,
    NotMentorError,
)
from app.services.invitation import (
    CohortFullError,
    DuplicateInvitationError,
    EmailAlreadyInCohortError,
    InvitationAlreadyUsedError,
    InvitationError,
    InvitationExpiredError,
    InvitationNotFoundError,
    UserAlreadyStudentError,
    accept_invitation,
    create_invitation,
    decline_invitation,
    get_public_info,
    list_invitations,
    list_my_invitations,
    revoke_invitation,
)


router = APIRouter(tags=["invitations"])


def _invitation_error_to_http(e: Exception) -> HTTPException:
    """Маппит доменные исключения в HTTPException."""
    if isinstance(
        e, (InvitationNotFoundError, CohortNotFoundError)
    ):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(
        e,
        (
            DuplicateInvitationError,
            EmailAlreadyInCohortError,
            InvitationAlreadyUsedError,
            UserAlreadyStudentError,
        ),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if isinstance(e, InvitationExpiredError):
        return HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
    if isinstance(e, (NotMentorError, NotCohortOwnerError)):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if isinstance(e, CohortFullError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if isinstance(e, InvitationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------- Ментор ----------

@router.post(
    "/cohorts/{cohort_id}/invitations",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить приглашение",
    responses={
        403: {"description": "Не владелец когорты"},
        404: {"description": "Когорта не найдена"},
        409: {"description": "Email занят или уже приглашён"},
    },
)
def create_invitation_endpoint(
    cohort_id: uuid.UUID,
    data: InvitationCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> InvitationRead:
    """
    Создаёт приглашение и отправляет email.

    Только владелец когорты или админ.
    """
    try:
        return create_invitation(db, cohort_id, data, user=current_user)
    except Exception as e:
        raise _invitation_error_to_http(e)


@router.get(
    "/cohorts/{cohort_id}/invitations",
    response_model=list[InvitationRead],
    summary="Список приглашений когорты",
)
def list_invitations_endpoint(
    cohort_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    status_filter: InvitationStatus | None = Query(
        None, alias="status", description="Фильтр по статусу"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[InvitationRead]:
    """Все приглашения конкретной когорты. Только владелец/админ."""
    try:
        return list_invitations(
            db,
            cohort_id,
            user=current_user,
            status=status_filter,
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        raise _invitation_error_to_http(e)


@router.delete(
    "/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отозвать приглашение",
)
def revoke_invitation_endpoint(
    invitation_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Отзывает pending-приглашение."""
    try:
        revoke_invitation(db, invitation_id, user=current_user)
    except Exception as e:
        raise _invitation_error_to_http(e)
    return None


# ---------- Пользователь ----------

@router.get(
    "/my/invitations",
    response_model=list[InvitationRead],
    summary="Мои приглашения",
)
def list_my_invitations_endpoint(
    db: DbSession,
    current_user: CurrentUser,
) -> list[InvitationRead]:
    """Все приглашения, отправленные на email текущего пользователя."""
    return list_my_invitations(db, user=current_user)


# ---------- Публичные (по токену) ----------

@router.get(
    "/invitations/info/{token}",
    response_model=InvitationPublicInfo,
    summary="Информация о приглашении (публичная)",
)
def get_invitation_info(
    token: str,
    db: DbSession,
) -> InvitationPublicInfo:
    """
    Публичная информация о приглашении по токену.

    Без авторизации. Не светим id, cohort_id, invited_by.
    """
    try:
        return get_public_info(db, token)
    except Exception as e:
        raise _invitation_error_to_http(e)


@router.post(
    "/invitations/accept/{token}",
    response_model=InvitationAcceptResponse,
    summary="Принять приглашение",
    responses={
        401: {"description": "Требуется авторизация"},
        403: {"description": "Email не совпадает"},
        404: {"description": "Приглашение не найдено"},
        409: {"description": "Уже принято / истекло / студент"},
        410: {"description": "Истекло"},
    },
)
def accept_invitation_endpoint(
    token: str,
    db: DbSession,
    current_user: CurrentUser,
) -> InvitationAcceptResponse:
    """
    Принимает приглашение.

    Эффекты:
    - роль: GUEST → STUDENT
    - добавление в CohortMember
    """
    try:
        invitation, member = accept_invitation(db, token, user=current_user)
    except Exception as e:
        raise _invitation_error_to_http(e)

    # Загружаем имя когорты для ответа
    from app.crud import cohort as cohort_crud

    cohort = cohort_crud.get_cohort_by_id(db, invitation.cohort_id)

    return InvitationAcceptResponse(
        user_id=current_user.id,
        cohort_id=invitation.cohort_id,
        cohort_name=cohort.name if cohort else "Unknown",
    )


@router.post(
    "/invitations/decline/{token}",
    response_model=InvitationRead,
    summary="Отклонить приглашение",
)
def decline_invitation_endpoint(
    token: str,
    db: DbSession,
    current_user: CurrentUser,
) -> InvitationRead:
    """Отклоняет приглашение."""
    try:
        return decline_invitation(db, token, user=current_user)
    except Exception as e:
        raise _invitation_error_to_http(e)
