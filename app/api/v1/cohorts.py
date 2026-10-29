"""
Эндпоинты для Cohort и CohortMember.
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.crud import cohort as cohort_crud
from app.schemas.cohort import (
    CohortCreate,
    CohortMemberAdd,
    CohortMemberRead,
    CohortRead,
    CohortReadWithMembers,
    CohortStats,
    CohortUpdate,
)
from app.services.cohort import (
    CohortError,
    CohortNameAlreadyExistsError,
    CohortNotFoundError,
    MemberAlreadyExistsError,
    MemberNotFoundError,
    NotCohortOwnerError,
    NotMentorError,
    StudentAlreadyInCohortError,
    UserNotFoundError,
    add_student,
    archive_cohort,
    check_cohort_owner,
    create_cohort,
    delete_cohort,
    get_cohort_stats,
    remove_member,
    update_cohort,
)


router = APIRouter(prefix="/cohorts", tags=["cohorts"])


def _cohort_error_to_http(e: Exception) -> HTTPException:
    """Маппит доменные исключения когорт в HTTPException."""
    if isinstance(e, (CohortNotFoundError, MemberNotFoundError, UserNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, (MemberAlreadyExistsError, StudentAlreadyInCohortError, CohortNameAlreadyExistsError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if isinstance(e, (NotMentorError, NotCohortOwnerError)):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if isinstance(e, CohortError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------- Список ----------

@router.get(
    "",
    response_model=list[CohortRead],
    summary="Список когорт",
)
def list_cohorts(
    db: DbSession,
    current_user: CurrentUser,
    include_archived: bool = Query(False, description="Включать архивные"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[CohortRead]:
    """
    Список когорт.

    - MENTOR видит свои когорты.
    - ADMIN видит все когорты.
    """
    from app.models.user import UserRole

    if current_user.role == UserRole.STUDENT:
        return cohort_crud.get_cohorts_by_student(
            db,
            student_id=current_user.id,
            skip=skip,
            limit=limit,
        )

    return cohort_crud.get_cohorts_by_mentor(
        db,
        mentor_id=current_user.id,
        include_archived=include_archived,
        skip=skip,
        limit=limit,
    )


# ---------- Создание ----------

@router.post(
    "",
    response_model=CohortRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать когорту",
    responses={403: {"description": "Только MENTOR или ADMIN"}},
)
def create_cohort_endpoint(
    data: CohortCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> CohortRead:
    """Создаёт когорту. Ментор автоматически становится её владельцем."""
    try:
        return create_cohort(db, data, user=current_user)
    except Exception as e:
        raise _cohort_error_to_http(e)


# ---------- Получить один ----------

@router.get(
    "/{cohort_id}",
    response_model=CohortReadWithMembers,
    summary="Получить когорту с участниками",
    responses={404: {"description": "Когорта не найдена"}},
)
def get_cohort(
    cohort_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> CohortReadWithMembers:
    """Когорта с участниками. Только владелец или админ."""
    try:
        cohort = check_cohort_owner(db, cohort_id, current_user)
    except Exception as e:
        raise _cohort_error_to_http(e)

    cohort.members = cohort_crud.get_members_by_cohort(db, cohort.id)
    return cohort


# ---------- Обновление ----------

@router.patch(
    "/{cohort_id}",
    response_model=CohortRead,
    summary="Обновить когорту",
)
def update_cohort_endpoint(
    cohort_id: uuid.UUID,
    data: CohortUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> CohortRead:
    """Обновляет когорту."""
    try:
        return update_cohort(db, cohort_id, data, user=current_user)
    except Exception as e:
        raise _cohort_error_to_http(e)


# ---------- Архивация ----------

@router.post(
    "/{cohort_id}/archive",
    response_model=CohortRead,
    summary="Архивировать когорту",
)
def archive_cohort_endpoint(
    cohort_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> CohortRead:
    """Архивирует когорту (soft delete)."""
    try:
        return archive_cohort(db, cohort_id, user=current_user)
    except Exception as e:
        raise _cohort_error_to_http(e)


# ---------- Удаление ----------

@router.delete(
    "/{cohort_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить когорту",
)
def delete_cohort_endpoint(
    cohort_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет когорту со всеми участниками."""
    try:
        delete_cohort(db, cohort_id, user=current_user)
    except Exception as e:
        raise _cohort_error_to_http(e)
    return None


# ---------- Участники ----------

@router.get(
    "/{cohort_id}/members",
    response_model=list[CohortMemberRead],
    summary="Список участников когорты",
)
@router.get(
    "/{cohort_id}/members",
    response_model=list[CohortMemberRead],
    summary="Список участников когорты",
)
def list_members(
    cohort_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[CohortMemberRead]:
    """
    Участники когорты.

    - MENTOR/ADMIN: только для своих когорт (owner).
    - STUDENT: только для своей когорты (где он участник).
    - GUEST: 404 (не светим существование).
    """
    from app.models.user import UserRole

    try:
        if current_user.role == UserRole.STUDENT:
            # Студент видит участников только своей когорты
            member = cohort_crud.get_member(db, cohort_id, current_user.id)
            if member is None:
                raise CohortNotFoundError(
                    f"Cohort {cohort_id} not found"
                )
        else:
            # Ментор/админ — только своих когорт
            check_cohort_owner(db, cohort_id, current_user)
    except Exception as e:
        raise _cohort_error_to_http(e)

    return cohort_crud.get_members_by_cohort(db, cohort_id)

@router.post(
    "/{cohort_id}/members",
    response_model=CohortMemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить студента в когорту",
    responses={
        404: {"description": "Когорта или пользователь не найден"},
        409: {"description": "Студент уже в другой когорте"},
    },
)
def add_member_endpoint(
    cohort_id: uuid.UUID,
    data: CohortMemberAdd,
    db: DbSession,
    current_user: CurrentUser,
) -> CohortMemberRead:
    """Добавляет студента в конкретную когорту."""
    try:
        return add_student(db, cohort_id, data.user_id, user=current_user)
    except Exception as e:
        raise _cohort_error_to_http(e)


@router.delete(
    "/{cohort_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить участника из когорты",
)
def remove_member_endpoint(
    cohort_id: uuid.UUID,
    member_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Удаляет участника. Владельца-ментора удалить нельзя."""
    try:
        remove_member(db, cohort_id, member_id, user=current_user)
    except Exception as e:
        raise _cohort_error_to_http(e)
    return None


# ---------- Статистика ----------

@router.get(
    "/{cohort_id}/stats",
    response_model=CohortStats,
    summary="Статистика когорты",
)
def cohort_stats(
    cohort_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> CohortStats:
    """Статистика когорты: студенты, менторы, заполненность."""
    try:
        return get_cohort_stats(db, cohort_id, user=current_user)
    except Exception as e:
        raise _cohort_error_to_http(e)
