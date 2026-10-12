"""
Бизнес-логика для проектов.

Правила:
- key должен быть уникален.
- Owner не может быть удалён из участников.
- Нельзя добавить пользователя дважды.
- Только owner или admin может редактировать/удалять проект.
"""

import uuid

from sqlalchemy.orm import Session

from app.crud import project as project_crud
from app.crud import user as user_crud
from app.models.project import Project, ProjectMember
from app.models.user import User, UserRole
from app.schemas.project import (
    ProjectCreate,
    ProjectMemberAdd,
    ProjectMemberUpdate,
    ProjectUpdate,
)


# ---------- Исключения ----------

class ProjectError(Exception):
    """Базовое исключение для ошибок проектов."""


class ProjectKeyAlreadyExistsError(ProjectError):
    """Проект с таким key уже существует."""


class ProjectNotFoundError(ProjectError):
    """Проект не найден."""


class NotProjectOwnerError(ProjectError):
    """Пользователь не owner и не admin."""


class MemberAlreadyExistsError(ProjectError):
    """Пользователь уже участник проекта."""


class MemberNotFoundError(ProjectError):
    """Участник не найден в проекте."""


class CannotRemoveOwnerError(ProjectError):
    """Нельзя удалить владельца из проекта."""


class UserNotFoundError(ProjectError):
    """Пользователь для добавления не найден."""


# ---------- Проверка прав ----------

def _is_owner_or_admin(project: Project, user: User) -> bool:
    """Owner проекта или глобальный admin могут всё."""
    return project.owner_id == user.id or user.role == UserRole.ADMIN


def check_project_access(
    db: Session,
    project_id: uuid.UUID,
    user: User,
) -> Project:
    """
    Проверяет, что проект существует и пользователь имеет к нему доступ.
    Возвращает проект или бросает исключение.

    Доступ есть, если:
    - user — глобальный admin, ИЛИ
    - user — участник проекта.
    """
    project = project_crud.get_project_by_id(db, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    if user.role == UserRole.ADMIN:
        return project

    member = project_crud.get_member(db, project_id, user.id)
    if member is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    return project


def check_project_owner(
    db: Session,
    project_id: uuid.UUID,
    user: User,
) -> Project:
    """
    Проверяет, что пользователь — owner или admin.
    Используется для операций редактирования/удаления.
    """
    project = project_crud.get_project_by_id(db, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    if not _is_owner_or_admin(project, user):
        raise NotProjectOwnerError("Only project owner or admin can perform this action")

    return project


# ---------- Создание / обновление / удаление ----------

def create_project(
    db: Session,
    data: ProjectCreate,
    owner: User,
) -> Project:
    """Создаёт проект с проверкой уникальности key."""
    existing = project_crud.get_project_by_key(db, data.key)
    if existing is not None:
        raise ProjectKeyAlreadyExistsError(f"Project with key '{data.key}' already exists")

    return project_crud.create_project(db, data, owner_id=owner.id)


def update_project(
    db: Session,
    project_id: uuid.UUID,
    data: ProjectUpdate,
    user: User,
) -> Project:
    """Обновляет проект. Только owner или admin."""
    project = check_project_owner(db, project_id, user)
    return project_crud.update_project(db, project, data)


def delete_project(
    db: Session,
    project_id: uuid.UUID,
    user: User,
) -> None:
    """Удаляет проект. Только owner или admin."""
    project = check_project_owner(db, project_id, user)
    project_crud.delete_project(db, project)


def archive_project(
    db: Session,
    project_id: uuid.UUID,
    user: User,
) -> Project:
    """Архивирует проект (soft delete)."""
    project = check_project_owner(db, project_id, user)
    return project_crud.update_project(db, project, ProjectUpdate(is_archived=True))


# ---------- Участники ----------

def add_member(
    db: Session,
    project_id: uuid.UUID,
    data: ProjectMemberAdd,
    user: User,
) -> ProjectMember:
    """
    Добавляет участника. Только owner или admin.

    Проверки:
    - проект существует и user — owner/admin;
    - добавляемый user существует;
    - его ещё нет в проекте.
    """
    project = check_project_owner(db, project_id, user)

    new_member_user = user_crud.get_user_by_id(db, data.user_id)
    if new_member_user is None:
        raise UserNotFoundError(f"User {data.user_id} not found")

    existing = project_crud.get_member(db, project.id, data.user_id)
    if existing is not None:
        raise MemberAlreadyExistsError(
            f"User {data.user_id} is already a member of project {project.key}"
        )

    return project_crud.add_member(db, project.id, data.user_id, data.role)


def update_member_role(
    db: Session,
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    data: ProjectMemberUpdate,
    user: User,
) -> ProjectMember:
    """Меняет роль участника. Только owner или admin."""
    check_project_owner(db, project_id, user)

    member = project_crud.get_member_by_id(db, member_id)
    if member is None or member.project_id != project_id:
        raise MemberNotFoundError(f"Member {member_id} not found in project {project_id}")

    return project_crud.update_member_role(db, member, data.role)


def remove_member(
    db: Session,
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    user: User,
) -> None:
    """
    Удаляет участника из проекта.

    Нельзя удалить владельца (owner) — иначе проект останется без хозяина.
    """
    project = check_project_owner(db, project_id, user)

    member = project_crud.get_member_by_id(db, member_id)
    if member is None or member.project_id != project_id:
        raise MemberNotFoundError(f"Member {member_id} not found in project {project_id}")

    if member.user_id == project.owner_id:
        raise CannotRemoveOwnerError("Cannot remove project owner from members")

    project_crud.remove_member(db, member)
