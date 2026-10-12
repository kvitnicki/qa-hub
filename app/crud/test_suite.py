"""
CRUD-операции для TestSuite.

Особенность: сьюты образуют дерево через parent_id.
При удалении сьюта — каскадно удаляются дети (за счёт FK CASCADE).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.test_suite import TestSuite
from app.schemas.test_suite import TestSuiteCreate, TestSuiteUpdate


def get_suite_by_id(db: Session, suite_id: uuid.UUID) -> TestSuite | None:
    """Находит сьют по id."""
    stmt = select(TestSuite).where(TestSuite.id == suite_id)
    return db.execute(stmt).scalar_one_or_none()


def get_suites_by_project(
    db: Session,
    project_id: uuid.UUID,
    parent_id: uuid.UUID | None = None,
    only_roots: bool = False,
) -> list[TestSuite]:
    """
    Возвращает сьюты проекта.

    - only_roots=True — только корневые (parent_id IS NULL).
    - parent_id=UUID — только дети конкретного сьюта.
    - без параметров — все сьюты проекта (плоский список).
    """
    stmt = select(TestSuite).where(TestSuite.project_id == project_id)

    if only_roots:
        stmt = stmt.where(TestSuite.parent_id.is_(None))
    elif parent_id is not None:
        stmt = stmt.where(TestSuite.parent_id == parent_id)

    stmt = stmt.order_by(TestSuite.order.asc(), TestSuite.created_at.asc())
    return list(db.execute(stmt).scalars().all())


def create_suite(
    db: Session,
    project_id: uuid.UUID,
    data: TestSuiteCreate,
    created_by: uuid.UUID,
) -> TestSuite:
    """Создаёт сьют."""
    suite = TestSuite(
        project_id=project_id,
        parent_id=data.parent_id,
        name=data.name,
        description=data.description,
        order=data.order,
        created_by=created_by,
    )
    db.add(suite)
    db.commit()
    db.refresh(suite)
    return suite


def update_suite(
    db: Session,
    suite: TestSuite,
    data: TestSuiteUpdate,
) -> TestSuite:
    """Обновляет сьют (PATCH-семантика)."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(suite, field, value)

    db.add(suite)
    db.commit()
    db.refresh(suite)
    return suite


def delete_suite(db: Session, suite: TestSuite) -> None:
    """Удаляет сьют. Дети удалятся каскадно (FK CASCADE)."""
    db.delete(suite)
    db.commit()
