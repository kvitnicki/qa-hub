"""
Бизнес-логика для Cohort и CohortMember.

Правила:
- Создавать когорты может MENTOR или ADMIN.
- При добавлении студента: если когорта переполнена — авто-создание новой.
- Студент только в 1 когорте.
- Управлять когортой может владелец-ментор или ADMIN.
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.crud import cohort as cohort_crud
from app.crud import user as user_crud
from app.models.cohort import Cohort, CohortMember, CohortRole
from app.models.user import User, UserRole
from app.schemas.cohort import (
    CohortCreate,
    CohortStats,
    CohortUpdate,
)


# ---------- Исключения ----------

class CohortError(Exception):
    """Базовое исключение для когорт."""


class CohortNotFoundError(CohortError):
    """Когорта не найдена."""


class MemberNotFoundError(CohortError):
    """Участник не найден."""

class CohortNameAlreadyExistsError(CohortError):
    """Когорта с таким именем у этого ментора уже есть."""

class NotMentorError(CohortError):
    """Только MENTOR или ADMIN могут создавать когорты."""


class NotCohortOwnerError(CohortError):
    """Только владелец-ментор или ADMIN может управлять когортой."""


class StudentAlreadyInCohortError(CohortError):
    """Студент уже в другой когорте."""


class MemberAlreadyExistsError(CohortError):
    """Участник уже в этой когорте."""


class UserNotFoundError(CohortError):
    """Пользователь не найден."""


class CannotAddMentorError(CohortError):
    """Менторов через add_member добавлять нельзя."""


MAX_STUDENTS_PER_COHORT = 5


# ---------- Проверки ----------

def _get_cohort_or_404(db: Session, cohort_id: uuid.UUID) -> Cohort:
    """Находит когорту или бросает CohortNotFoundError."""
    cohort = cohort_crud.get_cohort_by_id(db, cohort_id)
    if cohort is None:
        raise CohortNotFoundError(f"Cohort {cohort_id} not found")
    return cohort


def _is_cohort_owner_or_admin(cohort: Cohort, user: User) -> bool:
    """Владелец-ментор или админ."""
    return cohort.mentor_id == user.id or user.role == UserRole.ADMIN


def check_cohort_owner(db: Session, cohort_id: uuid.UUID, user: User) -> Cohort:
    """Проверяет, что user — владелец когорты или админ."""
    cohort = _get_cohort_or_404(db, cohort_id)

    if not _is_cohort_owner_or_admin(cohort, user):
        raise NotCohortOwnerError("Only cohort owner or admin can manage this cohort")

    return cohort


# ---------- Cohort ----------

def create_cohort(
    db: Session,
    data: CohortCreate,
    user: User,
) -> Cohort:
    """Создаёт когорту. Только MENTOR или ADMIN."""
    if user.role not in (UserRole.MENTOR, UserRole.ADMIN):
        raise NotMentorError(
            f"Only MENTOR or ADMIN can create cohorts (current role: {user.role.value})"
        )

    # Проверка уникальности имени в рамках ментора
    existing = cohort_crud.get_cohort_by_mentor_and_name(
        db, mentor_id=user.id, name=data.name
    )
    print (f"DEBUG: existing = {existing}, mentor_id = {user.id}, name = {data.name}")
    if existing is not None:
        raise CohortNameAlreadyExistsError(
            f"You already have a cohort named '{data.name}'. "
            f"Please choose a different name."
        )

    try:
        return cohort_crud.create_cohort(db, mentor_id=user.id, data=data)
    except IntegrityError as e:
        db.rollback()
        if "uq_cohorts_mentor_name" in str(e):
            raise CohortNameAlreadyExistsError(
                f"You already have a cohort named '{data.name}'. "
                f"Please choose a different name."
            ) from e
        raise

def update_cohort(
    db: Session,
    cohort_id: uuid.UUID,
    data: CohortUpdate,
    user: User,
) -> Cohort:
    """Обновляет когорту. Только владелец или админ."""
    cohort = check_cohort_owner(db, cohort_id, user)
    return cohort_crud.update_cohort(db, cohort, data)


def delete_cohort(
    db: Session,
    cohort_id: uuid.UUID,
    user: User,
) -> None:
    """Удаляет когорту. Только владелец или админ."""
    cohort = check_cohort_owner(db, cohort_id, user)
    cohort_crud.delete_cohort(db, cohort)


def archive_cohort(
    db: Session,
    cohort_id: uuid.UUID,
    user: User,
) -> Cohort:
    """Архивирует когорту (soft delete)."""
    cohort = check_cohort_owner(db, cohort_id, user)
    return cohort_crud.update_cohort(db, cohort, CohortUpdate(is_archived=True))


# ---------- Участники ----------

def add_student(
    db: Session,
    cohort_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User,
) -> CohortMember:
    """
    Добавляет студента в когорту.

    Проверки:
    - user — владелец когорты или админ;
    - добавляемый user существует;
    - добавляемый user ещё не студент ни в одной когорте;
    - добавляемый user ещё не в этой когорте;
    - в когорте меньше MAX_STUDENTS_PER_COHORT студентов.
    """
    cohort = check_cohort_owner(db, cohort_id, user)

    new_user = user_crud.get_user_by_id(db, user_id)
    if new_user is None:
        raise UserNotFoundError(f"User {user_id} not found")

    # Уже в этой когорте?
    existing_in_cohort = cohort_crud.get_member(db, cohort.id, user_id)
    if existing_in_cohort is not None:
        raise MemberAlreadyExistsError(
            f"User {user_id} is already a member of cohort {cohort_id}"
        )

    # Уже студент в другой когорте?
    existing_student = cohort_crud.get_student_cohort(db, user_id)
    if existing_student is not None:
        raise StudentAlreadyInCohortError(
            f"User {user_id} is already a student in another cohort"
        )

    # Место есть?
    students_count = cohort_crud.count_students(db, cohort.id)
    if students_count >= MAX_STUDENTS_PER_COHORT:
        raise CohortError(
            f"Cohort is full ({students_count}/{MAX_STUDENTS_PER_COHORT}). "
            f"Create a new cohort or use auto-add."
        )

    return cohort_crud.add_member(
        db, cohort_id=cohort.id, user_id=user_id, role=CohortRole.STUDENT
    )


def add_student_auto(
    db: Session,
    mentor_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User,
) -> tuple[Cohort, CohortMember]:
    """
    Добавляет студента в когорту ментора с авто-созданием.

    Если нет активной когорты с местом — создаёт новую.

    Возвращает (cohort, member).
    """
    # Ментор сам себя не добавляет
    if user.id != mentor_id and user.role != UserRole.ADMIN:
        raise NotCohortOwnerError("Only self or admin can use auto-add")

    new_user = user_crud.get_user_by_id(db, user_id)
    if new_user is None:
        raise UserNotFoundError(f"User {user_id} not found")

    # Уже в когорте?
    existing_student = cohort_crud.get_student_cohort(db, user_id)
    if existing_student is not None:
        raise StudentAlreadyInCohortError(
            f"User {user_id} is already a student in another cohort"
        )

    # Ищем когорту с местом
    cohort = cohort_crud.get_active_cohort_with_space(db, mentor_id)

    # Нет — создаём
    if cohort is None:
        n = len(cohort_crud.get_cohorts_by_mentor(db, mentor_id)) + 1
        cohort = cohort_crud.create_cohort(
            db,
            mentor_id=mentor_id,
            data=CohortCreate(name=f"Когорта {n}"),
        )

    member = cohort_crud.add_member(
        db, cohort_id=cohort.id, user_id=user_id, role=CohortRole.STUDENT
    )

    return cohort, member


def remove_member(
    db: Session,
    cohort_id: uuid.UUID,
    member_id: uuid.UUID,
    user: User,
) -> None:
    """Удаляет участника. Владельца-ментора удалить нельзя."""
    cohort = check_cohort_owner(db, cohort_id, user)

    member = cohort_crud.get_member_by_id(db, member_id)
    if member is None or member.cohort_id != cohort.id:
        raise MemberNotFoundError(f"Member {member_id} not found in cohort {cohort_id}")

    if member.user_id == cohort.mentor_id:
        raise CohortError("Cannot remove cohort owner")

    cohort_crud.remove_member(db, member)


# ---------- Stats ----------

def get_cohort_stats(
    db: Session,
    cohort_id: uuid.UUID,
    user: User,
) -> CohortStats:
    """Статистика когорты."""
    check_cohort_owner(db, cohort_id, user)

    students = cohort_crud.count_students(db, cohort_id)
    mentors = cohort_crud.count_mentors(db, cohort_id)

    return CohortStats(
        total_students=students,
        total_mentors=mentors,
        max_students=MAX_STUDENTS_PER_COHORT,
        is_full=students >= MAX_STUDENTS_PER_COHORT,
    )
