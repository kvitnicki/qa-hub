"""
Модель для заявок на роль ментора.

Пользователь (GUEST) подаёт заявку → админ проверяет → одобряет/отклоняет.
Если одобрено → роль пользователя меняется на MENTOR.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApplicationStatus(str, Enum):
    """Статус заявки на менторство."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExperienceLevel(str, Enum):
    """Опыт работы в QA."""

    JUNIOR = "0-1"   # 0–1 год
    MIDDLE = "1-3"   # 1–3 года
    SENIOR = "3-6"   # 3–6 лет


class MentorApplication(Base):
    """Заявка на роль ментора."""

    __tablename__ = "mentor_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_review', 'approved', 'rejected')",
            name="ck_mentor_applications_status_valid",
        ),
        CheckConstraint(
            "experience_level IN ('0-1', '1-3', '3-6')",
            name="ck_mentor_applications_experience_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SQLEnum(
            ApplicationStatus,
            name="mentor_application_status",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ApplicationStatus.PENDING,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        SQLEnum(
            ExperienceLevel,
            name="mentor_experience_level",
            native_enum=False,
            length=10,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tech_stack: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    testing_types: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    motivation: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<MentorApplication {self.id} [{self.status}]>"
