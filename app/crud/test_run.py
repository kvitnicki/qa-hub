"""
CRUD-операции для TestRun и TestResult.

Особенность: создание прогона включает массовое создание
результатов — по одному на каждый test_case_id.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.test_run import ResultStatus, RunStatus, TestResult, TestRun
from app.schemas.test_run import TestRunCreate, TestRunUpdate


# ---------- TestRun ----------

def get_run_by_id(db: Session, run_id: uuid.UUID) -> TestRun | None:
    """Находит прогон по id."""
    stmt = select(TestRun).where(TestRun.id == run_id)
    return db.execute(stmt).scalar_one_or_none()


def get_runs_by_project(
    db: Session,
    project_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[TestRun]:
    """Список прогонов проекта."""
    stmt = (
        select(TestRun)
        .where(TestRun.project_id == project_id)
        .order_by(TestRun.started_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def create_run(
    db: Session,
    project_id: uuid.UUID,
    data: TestRunCreate,
    started_by: uuid.UUID,
) -> TestRun:
    """
    Создаёт прогон и TestResult для каждого test_case_id.

    Все результаты создаются со статусом in_progress —
    их потом обновляют через API по мере выполнения.

    Всё в одной транзакции: либо создаётся прогон + все результаты,
    либо ничего.
    """
    run = TestRun(
        project_id=project_id,
        name=data.name,
        description=data.description,
        environment=data.environment,
        source=data.source,
        status=RunStatus.IN_PROGRESS,
        started_by=started_by,
    )
    db.add(run)
    db.flush()  # получаем run.id

    # Создаём результат на каждый кейс
    for case_id in data.test_case_ids:
        result = TestResult(
            test_run_id=run.id,
            test_case_id=case_id,
            status=ResultStatus.IN_PROGRESS,
            executed_by=started_by,
        )
        db.add(result)

    db.commit()
    db.refresh(run)
    return run


def update_run(
    db: Session,
    run: TestRun,
    data: TestRunUpdate,
) -> TestRun:
    """Обновляет прогон."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(run, field, value)

    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def delete_run(db: Session, run: TestRun) -> None:
    """Удаляет прогон. Результаты удалятся каскадно."""
    db.delete(run)
    db.commit()


# ---------- TestResult ----------

def get_result_by_id(db: Session, result_id: uuid.UUID) -> TestResult | None:
    """Находит результат по id."""
    stmt = select(TestResult).where(TestResult.id == result_id)
    return db.execute(stmt).scalar_one_or_none()


def get_result(
    db: Session,
    run_id: uuid.UUID,
    case_id: uuid.UUID,
) -> TestResult | None:
    """Находит результат по (run_id, case_id)."""
    stmt = select(TestResult).where(
        TestResult.test_run_id == run_id,
        TestResult.test_case_id == case_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_results_by_run(db: Session, run_id: uuid.UUID) -> list[TestResult]:
    """Все результаты прогона."""
    stmt = (
        select(TestResult)
        .where(TestResult.test_run_id == run_id)
        .order_by(TestResult.executed_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def update_result(
    db: Session,
    result: TestResult,
    status: ResultStatus | None = None,
    duration_ms: int | None = None,
    comment: str | None = None,
    attachments: dict | None = None,
    executed_by: uuid.UUID | None = None,
) -> TestResult:
    """
    Обновляет результат.

    Если executed_by передан — обновляем его тоже.
    """
    if status is not None:
        result.status = status
    if duration_ms is not None:
        result.duration_ms = duration_ms
    if comment is not None:
        result.comment = comment
    if attachments is not None:
        result.attachments = attachments
    if executed_by is not None:
        result.executed_by = executed_by

    db.add(result)
    db.commit()
    db.refresh(result)
    return result
