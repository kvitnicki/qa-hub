"""
Pydantic-схемы для Cohort и CohortMember.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.cohort import CohortRole
from app.schemas.user import UserShort


# ---------- Cohort ----------

class CohortBase(BaseModel):
    """Общие поля когорты."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Название когорты",
        examples=["QA-2026-Осень"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Описание когорты",
    )


class CohortCreate(CohortBase):
    """Схема для создания когорты."""

    pass


class CohortUpdate(BaseModel):
    """Схема для PATCH-обновления. Все поля опциональны."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_archived: bool | None = None


class CohortRead(CohortBase):
    """Схема для чтения когорты."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mentor_id: uuid.UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class CohortReadWithMembers(CohortRead):
    """Когорта с участниками."""

    members: list["CohortMemberRead"] = []


# ---------- CohortMember ----------

class CohortMemberAdd(BaseModel):
    """Схема для добавления участника (по user_id)."""

    user_id: uuid.UUID = Field(
        ...,
        description="ID пользователя для добавления",
    )
    role: CohortRole = Field(
        default=CohortRole.STUDENT,
        description="Роль в когорте",
    )


class CohortMemberRead(BaseModel):
    """Схема для чтения участника когорты."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cohort_id: uuid.UUID
    user_id: uuid.UUID
    role: CohortRole
    joined_at: datetime
    user: UserShort


# ---------- Stats ----------

class CohortStats(BaseModel):
    """Статистика когорты."""

    total_students: int = Field(description="Всего студентов")
    total_mentors: int = Field(description="Всего менторов")
    max_students: int = Field(default=5, description="Максимум студентов")
    is_full: bool = Field(description="Когорта заполнена")


# Разрешаем forward reference
CohortReadWithMembers.model_rebuild()
