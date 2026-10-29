"""
CRUD-операции для Cohort и CohortMember.

Правила:
- Студент может быть только в 1 когорте (partial unique index).
- Ментор может быть в нескольких.
- Max студентов на когорту — проверка в сервисе.
- Авто-создание при переполнении — в сервисе.
- Имя когорты уникально в рамках ментора.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cohort import Cohort, CohortMember, CohortRole
from app.schemas.cohort import CohortCreate, CohortUpdate


# ---------- Cohort ----------

def get_cohort_by_id(db: Session, cohort_id: uuid.UUID) -> Cohort | None:
    """Находит когорту по id."""
    stmt = select(Cohort).where(Cohort.id == cohort_id)
    return db.execute(stmt).scalar_one_or_none()


def get_cohort_by_mentor_and_name(
    db: Session,
    mentor_id: uuid.UUID,
    name: str,
) -> Cohort | None:
    """
    Находит когорту по ментору и имени.

    Используется для проверки уникальности имени в рамках ментора.
    """
    stmt = select(Cohort).where(
        Cohort.mentor_id == mentor_id,
        Cohort.name == name,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_cohorts_by_mentor(
    db: Session,
    mentor_id: uuid.UUID,
    include_archived: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> list[Cohort]:
    """Когорты ментора."""
    stmt = select(Cohort).where(Cohort.mentor_id == mentor_id)

    if not include_archived:
        stmt = stmt.where(Cohort.is_archived.is_(False))

    stmt = stmt.order_by(Cohort.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())

def get_cohorts_by_student(
    db: Session,
    student_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[Cohort]:
    """
    Когорты, где студент — участник.

    Используется для /cohorts, когда user.role == STUDENT.
    """
    stmt = (
        select(Cohort)
        .join(CohortMember, CohortMember.cohort_id == Cohort.id)
        .where(
            CohortMember.user_id == student_id,
            CohortMember.role == CohortRole.STUDENT,
        )
        .order_by(Cohort.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())

def get_active_cohort_with_space(
    db: Session,
    mentor_id: uuid.UUID,
    max_students: int = 5,
) -> Cohort | None:
    """
    Находит активную (не архивную) когорту ментора с местом (<max_students).
    """
    stmt = (
        select(Cohort)
        .where(
            Cohort.mentor_id == mentor_id,
            Cohort.is_archived.is_(False),
        )
        .order_by(Cohort.created_at.asc())
    )
    cohorts = list(db.execute(stmt).scalars().all())

    for cohort in cohorts:
        students_count = count_students(db, cohort.id)
        if students_count < max_students:
            return cohort

    return None


def count_students(db: Session, cohort_id: uuid.UUID) -> int:
    """Количество студентов в когорте."""
    stmt = select(func.count()).select_from(CohortMember).where(
        CohortMember.cohort_id == cohort_id,
        CohortMember.role == CohortRole.STUDENT,
    )
    return db.execute(stmt).scalar_one()


def count_mentors(db: Session, cohort_id: uuid.UUID) -> int:
    """Количество менторов в когорте (главный + ассистенты)."""
    stmt = select(func.count()).select_from(CohortMember).where(
        CohortMember.cohort_id == cohort_id,
        CohortMember.role == CohortRole.MENTOR,
    )
    return db.execute(stmt).scalar_one()


def create_cohort(
    db: Session,
    mentor_id: uuid.UUID,
    data: CohortCreate,
) -> Cohort:
    """Создаёт когорту и автоматически добавляет ментора как mentor-участника."""
    cohort = Cohort(
        mentor_id=mentor_id,
        name=data.name,
        description=data.description,
    )
    db.add(cohort)
    db.flush()

    member = CohortMember(
        cohort_id=cohort.id,
        user_id=mentor_id,
        role=CohortRole.MENTOR,
    )
    db.add(member)

    db.commit()
    db.refresh(cohort)
    return cohort


def update_cohort(
    db: Session,
    cohort: Cohort,
    data: CohortUpdate,
) -> Cohort:
    """Обновляет когорту."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cohort, field, value)

    db.add(cohort)
    db.commit()
    db.refresh(cohort)
    return cohort


def delete_cohort(db: Session, cohort: Cohort) -> None:
    """Удаляет когорту. Участники удалятся каскадно."""
    db.delete(cohort)
    db.commit()


# ---------- CohortMember ----------

def get_member_by_id(db: Session, member_id: uuid.UUID) -> CohortMember | None:
    """Находит участника по id."""
    stmt = select(CohortMember).where(CohortMember.id == member_id)
    return db.execute(stmt).scalar_one_or_none()


def get_member(
    db: Session,
    cohort_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CohortMember | None:
    """Находит участника по (cohort_id, user_id)."""
    stmt = select(CohortMember).where(
        CohortMember.cohort_id == cohort_id,
        CohortMember.user_id == user_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_members_by_cohort(
    db: Session,
    cohort_id: uuid.UUID,
) -> list[CohortMember]:
    """Все участники когорты."""
    stmt = (
        select(CohortMember)
        .where(CohortMember.cohort_id == cohort_id)
        .order_by(CohortMember.joined_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_student_cohort(
    db: Session,
    user_id: uuid.UUID,
) -> CohortMember | None:
    """Находит когорту, в которой user — студент."""
    stmt = select(CohortMember).where(
        CohortMember.user_id == user_id,
        CohortMember.role == CohortRole.STUDENT,
    )
    return db.execute(stmt).scalar_one_or_none()


def add_member(
    db: Session,
    cohort_id: uuid.UUID,
    user_id: uuid.UUID,
    role: CohortRole,
) -> CohortMember:
    """Добавляет участника в когорту."""
    member = CohortMember(
        cohort_id=cohort_id,
        user_id=user_id,
        role=role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, member: CohortMember) -> None:
    """Удаляет участника из когорты."""
    db.delete(member)
    db.commit()
