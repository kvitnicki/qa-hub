"""
Pydantic-схемы для TestSuite.

TestSuite — иерархическая структура. Для отдачи дерева используем
TestSuiteTree, где children — рекурсивный список.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TestSuiteBase(BaseModel):
    """Общие поля сьюта."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Название сьюта",
        examples=["Login Tests", "Registration"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Описание сьюта",
    )
    order: int = Field(
        default=0,
        ge=0,
        description="Порядок сортировки",
    )


class TestSuiteCreate(TestSuiteBase):
    """Схема для создания сьюта."""

    parent_id: uuid.UUID | None = Field(
        default=None,
        description="ID родительского сьюта",
    )


class TestSuiteUpdate(BaseModel):
    """Схема для PATCH-обновления."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    order: int | None = Field(default=None, ge=0)
    parent_id: uuid.UUID | None = None


class TestSuiteRead(TestSuiteBase):
    """Схема для чтения сьюта (без детей)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    parent_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TestSuiteTree(TestSuiteRead):
    """Схема для дерева: сьют + рекурсивно дети."""

    children: list["TestSuiteTree"] = []


# Разрешаем forward reference
TestSuiteTree.model_rebuild()
