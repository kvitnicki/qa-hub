"""
Пакет моделей SQLAlchemy.

ВАЖНО: Alembic при автогенерации миграций смотрит на Base.metadata
и видит только те модели, которые были ИМПОРТИРОВАНЫ.
Поэтому все модели нужно импортировать здесь.
"""

from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User, UserRole


__all__ = [
    "User",
    "UserRole",
    "Project",
    "ProjectMember",
    "ProjectRole",
]
