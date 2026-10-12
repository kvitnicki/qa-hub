"""
Pydantic-схемы для TestCase и TestStep.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.test_case import CaseStatus, CaseType, Priority, Severity


# ---------- TestStep ----------

class TestStepBase(BaseModel):
    """Общие поля шага."""

    order: int = Field(
        ...,
        ge=0,
        description="Номер шага",
        examples=[1],
    )
    action: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Действие",
        examples=["Ввести логин и пароль"],
    )
    expected_result: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Ожидаемый результат",
        examples=["Открывается главная страница"],
    )
    data: str | None = Field(
        default=None,
        max_length=2000,
        description="Тестовые данные",
    )


class TestStepCreate(BaseModel):
    """Схема для создания шага (order опционален — генерируется автоматически)."""

    order: int | None = Field(default=None, ge=0)
    action: str = Field(..., min_length=1, max_length=2000)
    expected_result: str = Field(..., min_length=1, max_length=2000)
    data: str | None = Field(default=None, max_length=2000)


class TestStepRead(TestStepBase):
    """Схема для чтения шага."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_case_id: uuid.UUID


# ---------- TestCase ----------

class TestCaseBase(BaseModel):
    """Общие поля тест-кейса."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Заголовок тест-кейса",
        examples=["Login with valid credentials"],
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Предусловия / описание",
    )
    priority: Priority = Field(default=Priority.MEDIUM)
    severity: Severity = Field(default=Severity.NORMAL)
    type: CaseType = Field(default=CaseType.FUNCTIONAL)
    status: CaseStatus = Field(default=CaseStatus.DRAFT)
    automated: bool = Field(default=False)


class TestCaseCreate(TestCaseBase):
    """Схема для создания тест-кейса."""

    suite_id: uuid.UUID | None = Field(
        default=None,
        description="ID сьюта (опционально)",
    )
    steps: list[TestStepCreate] = Field(
        default_factory=list,
        description="Шаги тест-кейса",
    )


class TestCaseUpdate(BaseModel):
    """Схема для PATCH-обновления."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    suite_id: uuid.UUID | None = None
    priority: Priority | None = None
    severity: Severity | None = None
    type: CaseType | None = None
    status: CaseStatus | None = None
    automated: bool | None = None


class TestCaseRead(TestCaseBase):
    """Схема для чтения тест-кейса (со шагами)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    suite_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    steps: list[TestStepRead] = []
