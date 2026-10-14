"""
Модель приглашения в когорту.

Ментор отправляет приглашение на email → студент принимает → становится STUDENT
и автоматически добавляется в когорту.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


if TYPE_CHECKING:
    from app.models.cohort import Cohort


class InvitationStatus(str, Enum):
    """Статус приглашения."""

    PENDING = "pending"      # Отправлено, ждёт ответа
    ACCEPTED = "accepted"    # Принято студентом
    DECLINED = "declined"    # Отклонено
    EXPIRED = "expired"      # Истекло (7 дней)
    REVOKED = "revoked"      # Отозвано ментором


def generate_token() -> str:
    """Генерирует криптографически стойкий токен (32 байта → 64 hex-символа)."""
    return secrets.token_urlsafe(32)


def default_expiry() -> datetime:
    """Через 7 дней от текущего момента (UTC)."""
    return datetime.now(timezone.utc) + timedelta(days=7)


class Invitation(Base):
    """
    Приглашение в когорту.

    Один email — одно активное приглашение (partial unique index).
    При принятии — user.role = STUDENT + добавление в CohortMember.
    """

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired', 'revoked')",
            name="ck_invitations_status_valid",
        ),
        # Одно активное приглашение на email
        Index(
            "ix_invitations_unique_pending_email",
            "email",
            unique=True,
            postgresql_where="status = 'pending'",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cohorts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    status: Mapped[InvitationStatus] = mapped_column(
        SQLEnum(
            InvitationStatus,
            name="invitation_status",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=InvitationStatus.PENDING,
        index=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=default_expiry
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Отношения
    cohort: Mapped["Cohort"] = relationship("Cohort", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Invitation {self.email} -> cohort={self.cohort_id} [{self.status}]>"

    @property
    def is_expired(self) -> bool:
        """Проверка истечения срока."""
        return datetime.now(timezone.utc) > self.expires_at
