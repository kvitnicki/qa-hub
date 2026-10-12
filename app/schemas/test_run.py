"""
Pydantic-схемы для TestRun и TestResult.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.test_run import ResultStatus, RunStatus


# ---------- TestRun ----------

class TestRunBase(BaseModel):
    """Общие поля прогона."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Название прогона",
        examples=["Nightly run 2026-10-13", "Release v1.2 smoke"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Описание прогона",
    )
    environment: str | None = Field(
        default=None,
        max_length=50,
        description="Окружение (dev/staging/prod)",
        examples=["staging"],
    )
    source: str | None = Field(
        default=None,
        max_length=50,
        description="Источник запуска (manual/ci_cd/api)",
        examples=["ci_cd"],
    )


class TestRunCreate(TestRunBase):
    """Схема для создания прогона."""

    test_case_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="ID тест-кейсов, которые включаются в прогон",
    )


class TestRunUpdate(BaseModel):
    """Схема для PATCH-обновления прогона."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: RunStatus | None = None
    environment: str | None = Field(default=None, max_length=50)
    source: str | None = Field(default=None, max_length=50)


class TestRunRead(TestRunBase):
    """Схема для чтения прогона (без результатов)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: RunStatus
    started_by: uuid.UUID
    started_at: datetime
    finished_at: datetime | None


class TestRunReadWithResults(TestRunRead):
    """Прогон с массивом результатов."""

    results: list["TestResultRead"] = []


# ---------- TestResult ----------

class TestResultBase(BaseModel):
    """Общие поля результата."""

    status: ResultStatus = Field(
        ...,
        description="Статус тест-кейса в прогоне",
    )
    duration_ms: int | None = Field(
        default=None,
        ge=0,
        description="Длительность выполнения в миллисекундах",
    )
    comment: str | None = Field(
        default=None,
        max_length=2000,
        description="Комментарий",
    )
    attachments: dict[str, Any] | None = Field(
        default=None,
        description="Вложения (ссылки на скриншоты, логи, видео)",
    )


class TestResultCreate(TestResultBase):
    """Схема для создания результата."""

    test_case_id: uuid.UUID


class TestResultUpdate(BaseModel):
    """Схема для PATCH-обновления результата."""

    status: ResultStatus | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    comment: str | None = Field(default=None, max_length=2000)
    attachments: dict[str, Any] | None = None


class TestResultRead(TestResultBase):
    """Схема для чтения результата."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_run_id: uuid.UUID
    test_case_id: uuid.UUID
    executed_by: uuid.UUID
    executed_at: datetime


class TestRunStats(BaseModel):
    """
    Статистика прогона.

    Возвращается отдельным эндпоинтом: /runs/{id}/stats.
    """

    total: int = Field(description="Всего тест-кейсов")
    passed: int = Field(description="Пройдено")
    failed: int = Field(description="Провалено")
    skipped: int = Field(description="Пропущено")
    blocked: int = Field(description="Заблокировано")
    in_progress: int = Field(description="В процессе")
    pass_rate: float = Field(
        description="Процент успешных (passed / (passed+failed)) * 100",
        examples=[85.5],
    )


# Разрешаем forward reference
TestRunReadWithResults.model_rebuild()
