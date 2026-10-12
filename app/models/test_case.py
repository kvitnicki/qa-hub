"""
Модели для тест-кейсов и их шагов.
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
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(str, Enum):
    MINOR = "minor"
    NORMAL = "normal"
    MAJOR = "major"
    CRITICAL = "critical"


class CaseType(str, Enum):
    FUNCTIONAL = "functional"
    REGRESSION = "regression"
    SMOKE = "smoke"
    INTEGRATION = "integration"
    E2E = "e2e"


class CaseStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class TestCase(Base):
    """Тест-кейс."""

    __tablename__ = "test_cases"
    __table_args__ = (
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="ck_test_cases_priority_valid",
        ),
        CheckConstraint(
            "severity IN ('minor', 'normal', 'major', 'critical')",
            name="ck_test_cases_severity_valid",
        ),
        CheckConstraint(
            "type IN ('functional', 'regression', 'smoke', 'integration', 'e2e')",
            name="ck_test_cases_type_valid",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'deprecated')",
            name="ck_test_cases_status_valid",
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
    suite_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[Priority] = mapped_column(
        SQLEnum(
            Priority,
            name="test_case_priority",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=Priority.MEDIUM,
    )
    severity: Mapped[Severity] = mapped_column(
        SQLEnum(
            Severity,
            name="test_case_severity",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=Severity.NORMAL,
    )
    type: Mapped[CaseType] = mapped_column(
        SQLEnum(
            CaseType,
            name="test_case_type",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=CaseType.FUNCTIONAL,
    )
    status: Mapped[CaseStatus] = mapped_column(
        SQLEnum(
            CaseStatus,
            name="test_case_status",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=CaseStatus.DRAFT,
        index=True,
    )
    automated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
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

    steps: Mapped[list["TestStep"]] = relationship(
        back_populates="test_case",
        cascade="all, delete-orphan",
        order_by="TestStep.order",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TestCase {self.title}>"


class TestStep(Base):
    """Шаг тест-кейса: действие → ожидаемый результат."""

    __tablename__ = "test_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[str | None] = mapped_column(Text, nullable=True)

    test_case: Mapped["TestCase"] = relationship(back_populates="steps")

    def __repr__(self) -> str:
        return f"<TestStep #{self.order}>"
