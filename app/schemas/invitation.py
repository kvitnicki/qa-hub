"""
Pydantic-схемы для Invitation.

Схемы:
- InvitationCreate — от ментора при создании приглашения.
- InvitationRead — для чтения (в списке).
- InvitationAcceptResponse — что возвращаем при принятии.
- InvitationPublicInfo — публичная информация (без авторизации, по токену).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.invitation import InvitationStatus


class InvitationCreate(BaseModel):
    """Схема для создания приглашения (от ментора)."""

    email: EmailStr = Field(
        ...,
        description="Email приглашённого",
        examples=["student@example.com"],
    )
    message: str | None = Field(
        default=None,
        max_length=1000,
        description="Сообщение от ментора",
        examples=["Привет! Приглашаю тебя в когорту QA-2026-Осень"],
    )


class InvitationRead(BaseModel):
    """Схема для чтения приглашения."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    cohort_id: uuid.UUID
    invited_by: uuid.UUID
    status: InvitationStatus
    message: str | None
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationPublicInfo(BaseModel):
    """
    Публичная информация по токену.

    Не требует авторизации — показывается при клике на ссылку.
    Без id, cohort_id, invited_by — только то, что нужно для отображения.
    """

    email: str
    cohort_name: str
    mentor_username: str
    message: str | None
    expires_at: datetime
    is_expired: bool


class InvitationAcceptResponse(BaseModel):
    """Ответ при принятии приглашения."""

    status: str = Field(default="accepted", examples=["accepted"])
    user_id: uuid.UUID
    cohort_id: uuid.UUID
    cohort_name: str
    message: str = Field(default="Welcome to the cohort!")
