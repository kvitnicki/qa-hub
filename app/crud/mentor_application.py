"""
CRUD-операции для MentorApplication.

Особенность: пользователь может иметь только одну активную заявку
(status='pending' или 'in_review') в момент времени.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mentor_application import (
    ApplicationStatus,
    MentorApplication,
)
from app.schemas.mentor_application import (
    MentorApplicationCreate,
    MentorApplicationUpdate,
)


def get_application_by_id(
    db: Session,
    application_id: uuid.UUID,
) -> MentorApplication | None:
    """Находит заявку по id."""
    stmt = select(MentorApplication).where(MentorApplication.id == application_id)
    return db.execute(stmt).scalar_one_or_none()


def get_active_application_by_user(
    db: Session,
    user_id: uuid.UUID,
) -> MentorApplication | None:
    """
    Находит активную (pending/in_review) заявку пользователя.

    Если у пользователя уже есть заявка в этих статусах — нельзя подавать новую.
    """
    stmt = select(MentorApplication).where(
        MentorApplication.user_id == user_id,
        MentorApplication.status.in_(
            [ApplicationStatus.PENDING, ApplicationStatus.IN_REVIEW]
        ),
    )
    return db.execute(stmt).scalar_one_or_none()


def get_applications_by_user(
    db: Session,
    user_id: uuid.UUID,
) -> list[MentorApplication]:
    """Все заявки пользователя (включая историю)."""
    stmt = (
        select(MentorApplication)
        .where(MentorApplication.user_id == user_id)
        .order_by(MentorApplication.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_applications(
    db: Session,
    status: ApplicationStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[MentorApplication]:
    """
    Список всех заявок (для админа).

    Можно фильтровать по статусу.
    """
    stmt = select(MentorApplication)

    if status is not None:
        stmt = stmt.where(MentorApplication.status == status)

    stmt = stmt.order_by(MentorApplication.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def create_application(
    db: Session,
    user_id: uuid.UUID,
    data: MentorApplicationCreate,
) -> MentorApplication:
    """Создаёт заявку со статусом pending."""
    # Преобразуем HttpUrl в str для JSONB совместимости
    application = MentorApplication(
        user_id=user_id,
        status=ApplicationStatus.PENDING,
        full_name=data.full_name,
        experience_level=data.experience_level,
        github_url=str(data.github_url) if data.github_url else None,
        linkedin_url=str(data.linkedin_url) if data.linkedin_url else None,
        tech_stack=data.tech_stack,
        testing_types=data.testing_types,
        motivation=data.motivation,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def update_application(
    db: Session,
    application: MentorApplication,
    data: MentorApplicationUpdate,
    reviewed_by: uuid.UUID | None = None,
) -> MentorApplication:
    """
    Обновляет заявку.

    Если статус меняется на approved/rejected — сохраняем reviewed_by и reviewed_at.
    """
    from datetime import datetime, timezone

    update_data = data.model_dump(exclude_unset=True)

    # Преобразуем HttpUrl → str
    if "github_url" in update_data and update_data["github_url"] is not None:
        update_data["github_url"] = str(update_data["github_url"])
    if "linkedin_url" in update_data and update_data["linkedin_url"] is not None:
        update_data["linkedin_url"] = str(update_data["linkedin_url"])

    for field, value in update_data.items():
        setattr(application, field, value)

    # Если статус финальный — записываем ревью
    if data.status in (ApplicationStatus.APPROVED, ApplicationStatus.REJECTED):
        application.reviewed_by = reviewed_by
        application.reviewed_at = datetime.now(timezone.utc)

    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def delete_application(
    db: Session,
    application: MentorApplication,
) -> None:
    """Удаляет заявку (только админ)."""
    db.delete(application)
    db.commit()
