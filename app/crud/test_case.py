"""
CRUD-операции для TestCase и TestStep.

Особенность TestCase: при создании передаются шаги (steps),
которые нужно создать каскадно в одной транзакции.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.test_case import TestCase, TestStep
from app.schemas.test_case import TestCaseCreate, TestCaseUpdate


# ---------- TestCase ----------

def get_case_by_id(db: Session, case_id: uuid.UUID) -> TestCase | None:
    """Находит тест-кейс по id."""
    stmt = select(TestCase).where(TestCase.id == case_id)
    return db.execute(stmt).scalar_one_or_none()


def get_cases_by_project(
    db: Session,
    project_id: uuid.UUID,
    suite_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[TestCase]:
    """
    Возвращает тест-кейсы проекта с фильтром по сьюту.

    - suite_id=None — все тест-кейсы проекта.
    - suite_id=UUID — только из конкретного сьюта.
    """
    stmt = select(TestCase).where(TestCase.project_id == project_id)

    if suite_id is not None:
        stmt = stmt.where(TestCase.suite_id == suite_id)

    stmt = (
        stmt.order_by(TestCase.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def create_case(
    db: Session,
    project_id: uuid.UUID,
    data: TestCaseCreate,
    created_by: uuid.UUID,
) -> TestCase:
    """
    Создаёт тест-кейс вместе с шагами.

    Шаги создаются в одной транзакции — если что-то упадёт,
    откатятся и тест-кейс, и шаги.
    """
    case = TestCase(
        project_id=project_id,
        suite_id=data.suite_id,
        title=data.title,
        description=data.description,
        priority=data.priority,
        severity=data.severity,
        type=data.type,
        status=data.status,
        automated=data.automated,
        created_by=created_by,
    )
    db.add(case)
    db.flush()  # получаем case.id до commit

    # Создаём шаги
    for idx, step_data in enumerate(data.steps, start=1):
        step = TestStep(
            test_case_id=case.id,
            order=step_data.order if step_data.order is not None else idx,
            action=step_data.action,
            expected_result=step_data.expected_result,
            data=step_data.data,
        )
        db.add(step)

    db.commit()
    db.refresh(case)
    return case


def update_case(
    db: Session,
    case: TestCase,
    data: TestCaseUpdate,
) -> TestCase:
    """Обновляет тест-кейс."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)

    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def delete_case(db: Session, case: TestCase) -> None:
    """Удаляет тест-кейс. Шаги удалятся каскадно."""
    db.delete(case)
    db.commit()


# ---------- TestStep ----------

def get_step_by_id(db: Session, step_id: uuid.UUID) -> TestStep | None:
    """Находит шаг по id."""
    stmt = select(TestStep).where(TestStep.id == step_id)
    return db.execute(stmt).scalar_one_or_none()


def get_steps_by_case(db: Session, case_id: uuid.UUID) -> list[TestStep]:
    """Все шаги тест-кейса, упорядоченные по order."""
    stmt = (
        select(TestStep)
        .where(TestStep.test_case_id == case_id)
        .order_by(TestStep.order.asc())
    )
    return list(db.execute(stmt).scalars().all())


def add_step(
    db: Session,
    case_id: uuid.UUID,
    order: int,
    action: str,
    expected_result: str,
    data: str | None = None,
) -> TestStep:
    """Добавляет шаг к тест-кейсу."""
    step = TestStep(
        test_case_id=case_id,
        order=order,
        action=action,
        expected_result=expected_result,
        data=data,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def delete_step(db: Session, step: TestStep) -> None:
    """Удаляет шаг."""
    db.delete(step)
    db.commit()
