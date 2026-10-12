"""
Модели для прогонов тестов (TestRun) и их результатов (TestResult).

TestRun — это "запуск" группы тест-кейсов:
    "Nightly run 2026-10-13" на staging
    "Release v1.2 smoke tests" на prod

TestResult — результат конкретного тест-кейса в рамках прогона.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RunStatus(str, Enum):
    """Статус прогона."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


class ResultStatus(str, Enum):
    """Статус отдельного тест-кейса в прогоне."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"


class TestRun(Base):
    """Прогон тест-кейсов."""

    __tablename__ = "test_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'aborted')",
            name="ck_test_runs_status_valid",
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
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        SQLEnum(
            RunStatus,
            name="test_run_status",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=RunStatus.IN_PROGRESS,
        index=True,
    )
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    results: Mapped[list["TestResult"]] = relationship(
        back_populates="test_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TestRun {self.name} [{self.status}]>"


class TestResult(Base):
    """Результат тест-кейса в рамках прогона."""

    __tablename__ = "test_results"
    __table_args__ = (
        UniqueConstraint(
            "test_run_id", "test_case_id", name="uq_test_results_run_case"
        ),
        CheckConstraint(
            "status IN ('passed', 'failed', 'skipped', 'blocked', 'in_progress')",
            name="ck_test_results_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    test_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ResultStatus] = mapped_column(
        SQLEnum(
            ResultStatus,
            name="test_result_status",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ResultStatus.IN_PROGRESS,
        index=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    executed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    test_run: Mapped["TestRun"] = relationship(back_populates="results")

    def __repr__(self) -> str:
        return f"<TestResult case={self.test_case_id} status={self.status}>"
