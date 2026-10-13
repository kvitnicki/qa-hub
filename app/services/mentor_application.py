"""
Бизнес-логика для MentorApplication.

Правила:
- Подать заявку может только GUEST.
- У пользователя не должно быть активной заявки.
- Одобрять/отклонять может только ADMIN.
- При одобрении роль пользователя меняется на MENTOR.
- Пользователь может отменить свою pending-заявку.
"""

import uuid

from sqlalchemy.orm import Session

from app.crud import mentor_application as app_crud
from app.crud import user as user_crud
from app.models.mentor_application import (
    ApplicationStatus,
    MentorApplication,
)
from app.models.user import User, UserRole
from app.schemas.mentor_application import (
    MentorApplicationCreate,
    MentorApplicationUpdate,
)


class MentorApplicationError(Exception):
    """Базовое исключение для заявок на менторство."""


class ApplicationNotFoundError(MentorApplicationError):
    """Заявка не найдена."""


class ApplicationAlreadyExistsError(MentorApplicationError):
    """У пользователя уже есть активная заявка."""


class InvalidApplicationStatusError(MentorApplicationError):
    """Нельзя выполнить операцию с заявкой в этом статусе."""


class NotGuestError(MentorApplicationError):
    """Подать заявку может только GUEST."""


class NotAdminError(MentorApplicationError):
    """Только ADMIN может одобрять/отклонять заявки."""


def _get_application_or_404(
    db: Session,
    application_id: uuid.UUID,
) -> MentorApplication:
    """Находит заявку или бросает ошибку."""
    application = app_crud.get_application_by_id(db, application_id)
    if application is None:
        raise ApplicationNotFoundError(f"Application {application_id} not found")
    return application


def submit_application(
    db: Session,
    data: MentorApplicationCreate,
    user: User,
) -> MentorApplication:
    """
    Подать заявку на менторство.

    Проверки:
    - пользователь должен быть GUEST;
    - у него не должно быть активной заявки.
    """
    if user.role != UserRole.GUEST:
        raise NotGuestError(
            f"Only GUEST can submit application (current role: {user.role.value})"
        )

    existing = app_crud.get_active_application_by_user(db, user.id)
    if existing is not None:
        raise ApplicationAlreadyExistsError(
            f"User already has an active application (status: {existing.status.value})"
        )

    return app_crud.create_application(db, user_id=user.id, data=data)


def get_my_applications(
    db: Session,
    user: User,
) -> list[MentorApplication]:
    """Все заявки текущего пользователя (история)."""
    return app_crud.get_applications_by_user(db, user.id)


def get_my_active_application(
    db: Session,
    user: User,
) -> MentorApplication | None:
    """Активная заявка текущего пользователя (если есть)."""
    return app_crud.get_active_application_by_user(db, user.id)


def cancel_my_application(
    db: Session,
    application_id: uuid.UUID,
    user: User,
) -> None:
    """
    Отменить свою pending-заявку.

    Можно отменить только в статусе pending и только свою.
    """
    application = _get_application_or_404(db, application_id)

    if application.user_id != user.id:
        raise ApplicationNotFoundError("Application not found")

    if application.status != ApplicationStatus.PENDING:
        raise InvalidApplicationStatusError(
            f"Can only cancel pending applications (current: {application.status.value})"
        )

    app_crud.delete_application(db, application)


# ---------- Для админа ----------

def list_applications(
    db: Session,
    admin: User,
    status: ApplicationStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[MentorApplication]:
    """Список заявок (только ADMIN)."""
    if admin.role != UserRole.ADMIN:
        raise NotAdminError("Only ADMIN can view applications")

    return app_crud.get_applications(db, status=status, skip=skip, limit=limit)


def approve_application(
    db: Session,
    application_id: uuid.UUID,
    admin: User,
) -> MentorApplication:
    """
    Одобрить заявку.

    Эффекты:
    - application.status = approved
    - application.reviewed_by = admin.id
    - application.reviewed_at = now
    - user.role = MENTOR
    """
    if admin.role != UserRole.ADMIN:
        raise NotAdminError("Only ADMIN can approve applications")

    application = _get_application_or_404(db, application_id)

    if application.status not in (ApplicationStatus.PENDING, ApplicationStatus.IN_REVIEW):
        raise InvalidApplicationStatusError(
            f"Can only approve pending/in_review (current: {application.status.value})"
        )

    # Обновляем заявку
    update_data = MentorApplicationUpdate(status=ApplicationStatus.APPROVED)
    application = app_crud.update_application(
        db, application, update_data, reviewed_by=admin.id
    )

    # Меняем роль пользователя
    user = user_crud.get_user_by_id(db, application.user_id)
    if user is not None:
        user.role = UserRole.MENTOR
        db.add(user)
        db.commit()
        db.refresh(application)

    return application


def reject_application(
    db: Session,
    application_id: uuid.UUID,
    admin: User,
    rejection_reason: str | None = None,
) -> MentorApplication:
    """
    Отклонить заявку.

    Эффекты:
    - application.status = rejected
    - application.rejection_reason = ...
    - application.reviewed_by = admin.id
    - user.role остаётся GUEST
    """
    if admin.role != UserRole.ADMIN:
        raise NotAdminError("Only ADMIN can reject applications")

    application = _get_application_or_404(db, application_id)

    if application.status not in (ApplicationStatus.PENDING, ApplicationStatus.IN_REVIEW):
        raise InvalidApplicationStatusError(
            f"Can only reject pending/in_review (current: {application.status.value})"
        )

    update_data = MentorApplicationUpdate(
        status=ApplicationStatus.REJECTED,
        rejection_reason=rejection_reason,
    )
    return app_crud.update_application(
        db, application, update_data, reviewed_by=admin.id
    )
