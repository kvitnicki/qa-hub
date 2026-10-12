"""
Модели для тест-сьютов (групп тест-кейсов).

TestSuite — иерархическая структура внутри проекта:
    Auth Suite
    ├── Login Tests
    ├── Registration Tests
    └── Password Reset
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TestSuite(Base):
    """
    Тест-сьют — группа тест-кейсов с возможностью вложенности.

    Поддерживает дерево через parent_id (self-referential FK).
    В корне проекта могут быть сьюты с parent_id=NULL.
    """

    __tablename__ = "test_suites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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

    children: Mapped[list["TestSuite"]] = relationship(
        "TestSuite",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    parent: Mapped["TestSuite | None"] = relationship(
        "TestSuite",
        back_populates="children",
        remote_side="TestSuite.id",
    )

    def __repr__(self) -> str:
        return f"<TestSuite {self.name}>"
