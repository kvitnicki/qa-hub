"""
Пакет моделей SQLAlchemy.

ВАЖНО: Alembic при автогенерации миграций смотрит на Base.metadata
и видит только те модели, которые были ИМПОРТИРОВАНЫ.
"""

from app.models.project import Project, ProjectMember, ProjectRole
from app.models.mentor_application import (
    ApplicationStatus,
    ExperienceLevel,
    MentorApplication,
)
from app.models.test_case import (
    CaseStatus,
    CaseType,
    Priority,
    Severity,
    TestCase,
    TestStep,
)
from app.models.test_run import ResultStatus, RunStatus, TestResult, TestRun
from app.models.test_suite import TestSuite
from app.models.user import User, UserRole
from app.models.cohort import Cohort, CohortMember, CohortRole
from app.models.invitation import Invitation, InvitationStatus
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
    # TestRun
    "TestRun",
    "TestResult",
    "RunStatus",
    "ResultStatus",
    # MentorApplication
    "MentorApplication",
    "ApplicationStatus",
    "ExperienceLevel",
    # Cohort
    "Cohort",
    "CohortMember",
    "CohortRole",
    # Invitation
    "Invitation",
    "InvitationStatus",
]
