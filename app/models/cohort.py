"""
Модели для когорт (групп студентов).

Cohort — группа студентов, привязанная к ментору.
CohortMember — участник когорты с ролью (mentor/student).

Правила:
- Студент может быть только в 1 когорте.
- Ментор может быть в нескольких когортах.
- Max 5 студентов на когорту (проверка в сервисе).
- Авто-создание при переполнении.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


if TYPE_CHECKING:
    from app.models.user import User


class CohortRole(str, Enum):
    """Роль участника в когорте."""

    MENTOR = "mentor"
    STUDENT = "student"


class Cohort(Base):
    """
    Когорта — группа студентов у ментора.

    Один ментор может иметь несколько когорт.
    Студенты распределяются по когортам (max 5 на когорту).
    """

    __tablename__ = "cohorts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mentor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Отношения
    members: Mapped[list["CohortMember"]] = relationship(
        back_populates="cohort",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Cohort {self.name}>"


class CohortMember(Base):
    """
    Участник когорты.

    Ограничения:
    - Студент только в одной когорте (partial unique).
    - Один участник один раз в когорте (composite unique).
    """

    __tablename__ = "cohort_members"
    __table_args__ = (
        # Один пользователь один раз в когорте
        UniqueConstraint(
            "cohort_id", "user_id", name="uq_cohort_members_cohort_user"
        ),
        # Студент только в одной когорте (partial unique index)
        Index(
            "ix_cohort_members_unique_student",
            "user_id",
            unique=True,
            postgresql_where="role = 'student'",
        ),
        # Валидация роли
        CheckConstraint(
            "role IN ('mentor', 'student')",
            name="ck_cohort_members_role_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cohorts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[CohortRole] = mapped_column(
        SQLEnum(
            CohortRole,
            name="cohort_role",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=CohortRole.STUDENT,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Отношения
    cohort: Mapped["Cohort"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<CohortMember cohort={self.cohort_id} user={self.user_id} role={self.role}>"
