"""
CRUD-операции для Project и ProjectMember.

Здесь только работа с БД. Бизнес-логика (проверки, права) — в services/.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMember, ProjectRole
from app.schemas.project import ProjectCreate, ProjectUpdate


# ---------- Project ----------

def get_project_by_id(db: Session, project_id: uuid.UUID) -> Project | None:
    """Находит проект по id."""
    stmt = select(Project).where(Project.id == project_id)
    return db.execute(stmt).scalar_one_or_none()


def get_project_by_key(db: Session, key: str) -> Project | None:
    """Находит проект по ключу (уникален)."""
    stmt = select(Project).where(Project.key == key)
    return db.execute(stmt).scalar_one_or_none()


def get_projects(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    owner_id: uuid.UUID | None = None,
) -> list[Project]:
    """
    Возвращает список проектов с фильтрами.

    - include_archived=False — по умолчанию не показываем архивные.
    - owner_id — фильтр по владельцу (для будущих нужд).
    """
    stmt = select(Project)

    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))

    if owner_id is not None:
        stmt = stmt.where(Project.owner_id == owner_id)

    stmt = stmt.order_by(Project.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def create_project(
    db: Session,
    data: ProjectCreate,
    owner_id: uuid.UUID,
) -> Project:
    """
    Создаёт проект и автоматически добавляет владельца как qa_lead.

    Это бизнес-правило: кто создал проект — тот в нём руководитель.
    Мы делаем это ЗДЕСЬ, потому что владелец — неотъемлемая часть создания.
    """
    project = Project(
        name=data.name,
        key=data.key,
        description=data.description,
        owner_id=owner_id,
    )
    db.add(project)
    db.flush()  # flush даёт project.id ДО commit, чтобы использовать его ниже

    # Добавляем owner'а как qa_lead
    member = ProjectMember(
        project_id=project.id,
        user_id=owner_id,
        role=ProjectRole.QA_LEAD,
    )
    db.add(member)

    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session,
    project: Project,
    data: ProjectUpdate,
) -> Project:
    """Обновляет поля проекта (PATCH-семантика)."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    """Удаляет проект. Участники удалятся каскадно."""
    db.delete(project)
    db.commit()


# ---------- ProjectMember ----------

def get_member(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ProjectMember | None:
    """Находит участника проекта по project_id и user_id."""
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_member_by_id(db: Session, member_id: uuid.UUID) -> ProjectMember | None:
    """Находит участника по id записи."""
    stmt = select(ProjectMember).where(ProjectMember.id == member_id)
    return db.execute(stmt).scalar_one_or_none()


def get_members(db: Session, project_id: uuid.UUID) -> list[ProjectMember]:
    """Все участники проекта."""
    stmt = (
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def add_member(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role: ProjectRole,
) -> ProjectMember:
    """Добавляет участника в проект."""
    member = ProjectMember(
        project_id=project_id,
        user_id=user_id,
        role=role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def update_member_role(
    db: Session,
    member: ProjectMember,
    role: ProjectRole,
) -> ProjectMember:
    """Обновляет роль участника."""
    member.role = role
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, member: ProjectMember) -> None:
    """Удаляет участника из проекта."""
    db.delete(member)
    db.commit()
