"""
Бизнес-логика для TestRun и TestResult.

Правила:
- Прогон принадлежит проекту.
- Все test_case_ids должны принадлежать тому же проекту.
- Статистика вычисляется на основе результатов.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.crud import test_case as case_crud
from app.crud import test_run as run_crud
from app.models.test_run import ResultStatus, RunStatus, TestResult, TestRun
from app.models.user import User
from app.schemas.test_run import TestRunCreate, TestRunStats, TestRunUpdate
from app.services.project import check_project_access


class RunError(Exception):
    """Базовое исключение для прогонов."""


class RunNotFoundError(RunError):
    """Прогон не найден."""


class ResultNotFoundError(RunError):
    """Результат не найден."""


class InvalidTestCaseError(RunError):
    """Тест-кейс не принадлежит проекту."""


def _get_run_or_404(
    db: Session,
    run_id: uuid.UUID,
    project_id: uuid.UUID,
) -> TestRun:
    """Находит прогон или бросает RunNotFoundError."""
    run = run_crud.get_run_by_id(db, run_id)
    if run is None or run.project_id != project_id:
        raise RunNotFoundError(f"TestRun {run_id} not found in project {project_id}")
    return run


def _validate_test_cases(
    db: Session,
    case_ids: list[uuid.UUID],
    project_id: uuid.UUID,
) -> None:
    """
    Проверяет, что все test_case_ids принадлежат проекту.

    Если хотя бы один кейс не найден или из другого проекта —
    бросаем InvalidTestCaseError.
    """
    for case_id in case_ids:
        case = case_crud.get_case_by_id(db, case_id)
        if case is None or case.project_id != project_id:
            raise InvalidTestCaseError(
                f"TestCase {case_id} not found in project {project_id}"
            )


def create_run(
    db: Session,
    project_id: uuid.UUID,
    data: TestRunCreate,
    user: User,
) -> TestRun:
    """
    Создаёт прогон с проверками:
    - доступ к проекту;
    - все кейсы принадлежат проекту.
    """
    check_project_access(db, project_id, user)
    _validate_test_cases(db, data.test_case_ids, project_id)

    return run_crud.create_run(db, project_id, data, started_by=user.id)


def update_run(
    db: Session,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    data: TestRunUpdate,
    user: User,
) -> TestRun:
    """
    Обновляет прогон.

    Если статус меняется на completed/aborted и finished_at не установлен —
    автоматически ставим finished_at = now().
    """
    check_project_access(db, project_id, user)
    run = _get_run_or_404(db, run_id, project_id)

    # Если завершаем прогон — фиксируем время

    if data.status in (RunStatus.COMPLETED, RunStatus.ABORTED):
        if run.finished_at is None:
            run.finished_at = datetime.now(timezone.utc)
    return run_crud.update_run(db, run, data)


def delete_run(
    db: Session,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    user: User,
) -> None:
    """Удаляет прогон. Результаты удалятся каскадно."""
    check_project_access(db, project_id, user)
    run = _get_run_or_404(db, run_id, project_id)
    run_crud.delete_run(db, run)


# ---------- Результаты ----------

def update_result_status(
    db: Session,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    result_id: uuid.UUID,
    status: ResultStatus | None,
    duration_ms: int | None,
    comment: str | None,
    attachments: dict | None,
    user: User,
) -> TestResult:
    """
    Обновляет результат тест-кейса в прогоне.

    Также проверяет: если все результаты больше не in_progress —
    автоматически завершает прогон.
    """
    check_project_access(db, project_id, user)
    run = _get_run_or_404(db, run_id, project_id)

    result = run_crud.get_result_by_id(db, result_id)
    if result is None or result.test_run_id != run.id:
        raise ResultNotFoundError(
            f"Result {result_id} not found in run {run_id}"
        )

    result = run_crud.update_result(
        db,
        result,
        status=status,
        duration_ms=duration_ms,
        comment=comment,
        attachments=attachments,
        executed_by=user.id,
    )

    # Автозавершение прогона
    if status is not None:
        _maybe_finish_run(db, run)

    return result


def _maybe_finish_run(db: Session, run: TestRun) -> None:
    """
    Если все результаты не in_progress — прогон завершён.

    Обновляет run.status = completed, run.finished_at = now().
    """
    results = run_crud.get_results_by_run(db, run.id)

    if not results:
        return  # пустой прогон не завершаем

    all_done = all(r.status != ResultStatus.IN_PROGRESS for r in results)
    if all_done and run.status == RunStatus.IN_PROGRESS:
        run.status = RunStatus.COMPLETED
        run.finished_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        db.refresh(run)

# ---------- Статистика ----------

def get_run_stats(
    db: Session,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    user: User,
) -> TestRunStats:
    """
    Считает статистику прогона.

    pass_rate = passed / (passed + failed) * 100.
    Если passed + failed == 0 — pass_rate = 0.
    """
    check_project_access(db, project_id, user)
    run = _get_run_or_404(db, run_id, project_id)

    results = run_crud.get_results_by_run(db, run.id)

    passed = sum(1 for r in results if r.status == ResultStatus.PASSED)
    failed = sum(1 for r in results if r.status == ResultStatus.FAILED)
    skipped = sum(1 for r in results if r.status == ResultStatus.SKIPPED)
    blocked = sum(1 for r in results if r.status == ResultStatus.BLOCKED)
    in_progress = sum(1 for r in results if r.status == ResultStatus.IN_PROGRESS)

    denominator = passed + failed
    pass_rate = (passed / denominator * 100) if denominator > 0 else 0.0

    return TestRunStats(
        total=len(results),
        passed=passed,
        failed=failed,
        skipped=skipped,
        blocked=blocked,
        in_progress=in_progress,
        pass_rate=round(pass_rate, 2),
    )
