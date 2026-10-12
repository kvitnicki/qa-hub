"""
Pydantic-схемы для проектов и участников.

Схемы разделены по назначению:
- ProjectCreate — что клиент присылает при создании.
- ProjectUpdate — что клиент может обновить (PATCH).
- ProjectRead — что мы возвращаем.
- ProjectMemberAdd/Read/Update — то же для участников.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectRole
from app.schemas.user import UserShort


# ---------- Project ----------

class ProjectBase(BaseModel):
    """Общие поля проекта."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Название проекта",
        examples=["QA Automation", "Mobile App"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Описание проекта",
    )


class ProjectCreate(ProjectBase):
    """Схема для создания проекта."""

    key: str = Field(
        ...,
        min_length=2,
        max_length=10,
        pattern=r"^[A-Z][A-Z0-9_-]*$",
        description="Короткий код проекта (заглавные буквы, цифры, _ и -)",
        examples=["AUTH", "PAY-V2", "MOBILE"],
    )


class ProjectUpdate(BaseModel):
    """Схема для PATCH-обновления проекта. Все поля опциональны."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_archived: bool | None = None


class ProjectRead(ProjectBase):
    """Схема для чтения проекта."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    owner_id: uuid.UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class ProjectReadWithMembers(ProjectRead):
    """Проект со списком участников."""

    members: list["ProjectMemberRead"] = []


# ---------- ProjectMember ----------

class ProjectMemberAdd(BaseModel):
    """Схема для добавления участника в проект."""

    user_id: uuid.UUID = Field(
        ...,
        description="ID пользователя для добавления",
    )
    role: ProjectRole = Field(
        default=ProjectRole.TESTER,
        description="Роль в проекте",
    )


class ProjectMemberUpdate(BaseModel):
    """Схема для обновления роли участника."""

    role: ProjectRole


class ProjectMemberRead(BaseModel):
    """Схема для чтения участника."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: ProjectRole
    joined_at: datetime
    user: UserShort


# Разрешаем forward reference: ProjectMemberRead определён ниже,
# но используется в ProjectReadWithMembers выше.
ProjectReadWithMembers.model_rebuild()
