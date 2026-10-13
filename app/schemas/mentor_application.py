"""
Pydantic-схемы для MentorApplication.

Схемы разделены:
- MentorApplicationCreate — что присылает пользователь при подаче.
- MentorApplicationUpdate — что может менять админ при ревью.
- MentorApplicationRead — что возвращаем.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.mentor_application import ApplicationStatus, ExperienceLevel


class MentorApplicationCreate(BaseModel):
    """
    Схема для подачи заявки на менторство.

    Все основные поля обязательны, кроме ссылок и дополнительной информации.
    """

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="ФИО",
        examples=["Иван Петров"],
    )
    experience_level: ExperienceLevel = Field(
        ...,
        description="Опыт работы в QA",
    )
    github_url: HttpUrl | None = Field(
        default=None,
        description="Ссылка на GitHub",
    )
    linkedin_url: HttpUrl | None = Field(
        default=None,
        description="Ссылка на LinkedIn",
    )
    tech_stack: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Технологии, с которыми работал",
        examples=[["pytest", "postman", "selenium"]],
    )
    testing_types: list[str] | None = Field(
        default=None,
        max_length=20,
        description="Виды тестирования",
        examples=[["functional", "regression", "load"]],
    )
    motivation: str | None = Field(
        default=None,
        max_length=2000,
        description="Почему хочет быть ментором",
    )


class MentorApplicationUpdate(BaseModel):
    """
    Схема для обновления заявки.

    Используется:
    - админом для одобрения/отклонения;
    - пользователем для редактирования своей pending-заявки.
    """

    status: ApplicationStatus | None = None
    rejection_reason: str | None = Field(default=None, max_length=2000)
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    experience_level: ExperienceLevel | None = None
    github_url: HttpUrl | None = None
    linkedin_url: HttpUrl | None = None
    tech_stack: list[str] | None = None
    testing_types: list[str] | None = None
    motivation: str | None = Field(default=None, max_length=2000)


class MentorApplicationRead(BaseModel):
    """Схема для чтения заявки."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: ApplicationStatus
    full_name: str
    experience_level: ExperienceLevel
    github_url: str | None
    linkedin_url: str | None
    tech_stack: list[str] | None
    testing_types: list[str] | None
    motivation: str | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
