"""
CRUD-операции для Invitation.

Особенности:
- Token генерируется автоматически.
- Одно активное приглашение на email (partial unique).
- Принятие меняет статус + добавляет в когорту (делается в сервисе).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invitation import (
    Invitation,
    InvitationStatus,
    generate_token,
)
from app.schemas.invitation import InvitationCreate


def get_invitation_by_id(
    db: Session, invitation_id: uuid.UUID
) -> Invitation | None:
    """Находит приглашение по id."""
    stmt = select(Invitation).where(Invitation.id == invitation_id)
    return db.execute(stmt).scalar_one_or_none()


def get_invitation_by_token(db: Session, token: str) -> Invitation | None:
    """Находит приглашение по токену."""
    stmt = select(Invitation).where(Invitation.token == token)
    return db.execute(stmt).scalar_one_or_none()


def get_pending_invitation_by_email(
    db: Session, email: str
) -> Invitation | None:
    """
    Находит активное (pending) приглашение по email.

    Гарантированно одно (partial unique index).
    """
    stmt = select(Invitation).where(
        Invitation.email == email,
        Invitation.status == InvitationStatus.PENDING,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_invitations_by_cohort(
    db: Session,
    cohort_id: uuid.UUID,
    status: InvitationStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Invitation]:
    """Приглашения когорты."""
    stmt = select(Invitation).where(Invitation.cohort_id == cohort_id)

    if status is not None:
        stmt = stmt.where(Invitation.status == status)

    stmt = stmt.order_by(Invitation.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_invitations_for_email(
    db: Session, email: str
) -> list[Invitation]:
    """
    Все приглашения для конкретного email.

    Используется для /my/invitations — чтобы пользователь видел свои приглашения.
    """
    stmt = (
        select(Invitation)
        .where(Invitation.email == email)
        .order_by(Invitation.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def create_invitation(
    db: Session,
    cohort_id: uuid.UUID,
    data: InvitationCreate,
    invited_by: uuid.UUID,
) -> Invitation:
    """Создаёт приглашение с автоматическим токеном и сроком."""
    invitation = Invitation(
        email=data.email,
        cohort_id=cohort_id,
        invited_by=invited_by,
        token=generate_token(),
        status=InvitationStatus.PENDING,
        message=data.message,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


def update_status(
    db: Session,
    invitation: Invitation,
    status: InvitationStatus,
) -> Invitation:
    """
    Обновляет статус приглашения.

    Если статус = accepted — ставит accepted_at.
    """
    invitation.status = status

    if status == InvitationStatus.ACCEPTED:
        invitation.accepted_at = datetime.now(timezone.utc)

    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


def delete_invitation(db: Session, invitation: Invitation) -> None:
    """Удаляет приглашение."""
    db.delete(invitation)
    db.commit()
