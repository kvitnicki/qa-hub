"""
Пакет моделей SQLAlchemy.

ВАЖНО: Alembic при автогенерации миграций смотрит на Base.metadata
и видит только те модели, которые были ИМПОРТИРОВАНЫ.
Поэтому все модели нужно импортировать здесь.
"""

from app.models.project import Project, ProjectMember, ProjectRole
from app.models.test_case import (
    CaseStatus,
    CaseType,
    Priority,
    Severity,
    TestCase,
    TestStep,
)
from app.models.test_suite import TestSuite
from app.models.user import User, UserRole


__all__ = [
    # User
    "User",
    "UserRole",
    # Project
    "Project",
    "ProjectMember",
    "ProjectRole",
    # TestSuite
    "TestSuite",
    # TestCase
    "TestCase",
    "TestStep",
    "Priority",
    "Severity",
    "CaseType",
    "CaseStatus",
]
