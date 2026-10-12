"""
Модели для проектов и участников проектов.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

class ProjectRole(str, Enum):
    """Роли пользователя В РАМКАХ проекта."""

    QA_LEAD = "qa_lead"
    TESTER = "tester"
    VIEWER = "viewer"


class Project(Base):
    """Проект — контейнер для тест-кейсов, сьютов, ранов."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "length(key) >= 2 AND length(key) <= 10",
            name="ck_projects_key_length",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key: Mapped[str] = mapped_column(
        String(10), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
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

    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Project {self.key}: {self.name}>"


class ProjectMember(Base):
    """Участник проекта с ролью."""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "user_id", name="uq_project_members_project_user"
        ),
        CheckConstraint(
            "role IN ('qa_lead', 'tester', 'viewer')",
            name="ck_project_members_role_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[ProjectRole] = mapped_column(
        SQLEnum(
            ProjectRole,
            name="project_role",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ProjectRole.TESTER,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<ProjectMember project={self.project_id} "
            f"user={self.user_id} role={self.role}>"
        )
