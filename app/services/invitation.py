"""
Бизнес-логика для Invitation.

Правила:
- Приглашать может только MENTOR (владелец когорты) или ADMIN.
- Нельзя пригласить email, который уже в другой когорте (студент не может быть в 2+).
- Нельзя иметь два pending-приглашения на один email (partial unique).
- При переполнении когорты — авто-создание новой (если разрешено).
- При принятии: role GUEST → STUDENT, добавление в CohortMember.
"""

import uuid

from sqlalchemy.orm import Session

from app.crud import cohort as cohort_crud
from app.crud import invitation as invitation_crud
from app.crud import user as user_crud
from app.models.cohort import CohortMember, CohortRole
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User, UserRole
from app.schemas.invitation import InvitationCreate, InvitationPublicInfo
from app.services.cohort import (
    MAX_STUDENTS_PER_COHORT,
    check_cohort_owner,
)


class InvitationError(Exception):
    """Базовое исключение для приглашений."""


class InvitationNotFoundError(InvitationError):
    """Приглашение не найдено."""


class InvitationExpiredError(InvitationError):
    """Приглашение истекло."""


class InvitationAlreadyUsedError(InvitationError):
    """Приглашение уже принято/отклонено/отозвано."""


class EmailAlreadyInCohortError(InvitationError):
    """Email уже занят в другой когорте."""


class DuplicateInvitationError(InvitationError):
    """Уже есть активное приглашение на этот email."""


class CohortFullError(InvitationError):
    """Когорта заполнена, авто-создание не разрешено."""


class UserAlreadyStudentError(InvitationError):
    """Пользователь уже студент."""


# ---------- Приглашение ----------

def _get_invitation_or_404(
    db: Session, invitation_id: uuid.UUID
) -> Invitation:
    invitation = invitation_crud.get_invitation_by_id(db, invitation_id)
    if invitation is None:
        raise InvitationNotFoundError(f"Invitation {invitation_id} not found")
    return invitation


def _mark_expired_if_needed(
    db: Session, invitation: Invitation
) -> Invitation:
    """Обновляет статус, если истекло."""
    if (
        invitation.status == InvitationStatus.PENDING
        and invitation.is_expired
    ):
        return invitation_crud.update_status(
            db, invitation, InvitationStatus.EXPIRED
        )
    return invitation


def create_invitation(
    db: Session,
    cohort_id: uuid.UUID,
    data: InvitationCreate,
    user: User,
) -> Invitation:
    """
    Создаёт приглашение.

    Проверки:
    - user — владелец когорты или админ;
    - email не занят студентом в другой когорте;
    - нет активного приглашения на этот email.
    """
    cohort = check_cohort_owner(db, cohort_id, user)

    # Email уже студент (в любой когорте)?
    existing_user = user_crud.get_user_by_email(db, data.email)
    if existing_user is not None:
        existing_member = cohort_crud.get_student_cohort(db, existing_user.id)
        if existing_member is not None:
            raise EmailAlreadyInCohortError(
                f"Email {data.email} is already a student"
            )    
# Email уже студент (в любой когорте)?
    existing_user = user_crud.get_user_by_email(db, data.email)
    if existing_user is not None:
        existing_member = cohort_crud.get_student_cohort(db, existing_user.id)
        if existing_member is not None:
            raise EmailAlreadyInCohortError(
                f"Email {data.email} is already a student"
            )
    # Уже есть pending-приглашение?
    existing_invitation = invitation_crud.get_pending_invitation_by_email(
        db, data.email
    )
    if existing_invitation is not None:
        raise DuplicateInvitationError(
            f"There is already a pending invitation for {data.email}"
        )

    return invitation_crud.create_invitation(
        db, cohort_id=cohort.id, data=data, invited_by=user.id
    )


def list_invitations(
    db: Session,
    cohort_id: uuid.UUID,
    user: User,
    status: InvitationStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Invitation]:
    """Список приглашений когорты (только владелец/админ)."""
    check_cohort_owner(db, cohort_id, user)

    invitations = invitation_crud.get_invitations_by_cohort(
        db, cohort_id, status=status, skip=skip, limit=limit
    )

    # Обновляем истёкшие
    return [_mark_expired_if_needed(db, inv) for inv in invitations]


def list_my_invitations(
    db: Session,
    user: User,
) -> list[Invitation]:
    """
    Мои приглашения (по email пользователя).

    Включая истёкшие (с обновлением статуса).
    """
    invitations = invitation_crud.get_invitations_for_email(db, user.email)
    return [_mark_expired_if_needed(db, inv) for inv in invitations]


def revoke_invitation(
    db: Session,
    invitation_id: uuid.UUID,
    user: User,
) -> None:
    """
    Отзывает приглашение (только владелец когорты/админ).

    Отозвать можно только pending.
    """
    invitation = _get_invitation_or_404(db, invitation_id)
    invitation = _mark_expired_if_needed(db, invitation)

    # Проверяем, что user — владелец когорты или админ
    check_cohort_owner(db, invitation.cohort_id, user)

    if invitation.status != InvitationStatus.PENDING:
        raise InvitationAlreadyUsedError(
            f"Cannot revoke invitation in status {invitation.status.value}"
        )

    invitation_crud.update_status(db, invitation, InvitationStatus.REVOKED)


# ---------- Публичная информация по токену ----------

def get_public_info(
    db: Session, token: str
) -> InvitationPublicInfo:
    """
    Публичная информация по токену (без авторизации).

    Возвращает только безопасные данные: имя когорты, ментора, сообщение.
    """
    invitation = invitation_crud.get_invitation_by_token(db, token)
    if invitation is None:
        raise InvitationNotFoundError("Invitation not found")

    invitation = _mark_expired_if_needed(db, invitation)

    # Загружаем связи
    cohort = cohort_crud.get_cohort_by_id(db, invitation.cohort_id)
    mentor = user_crud.get_user_by_id(db, invitation.invited_by)

    return InvitationPublicInfo(
        email=invitation.email,
        cohort_name=cohort.name if cohort else "Unknown",
        mentor_username=mentor.username if mentor else "Unknown",
        message=invitation.message,
        expires_at=invitation.expires_at,
        is_expired=invitation.status == InvitationStatus.EXPIRED,
    )


# ---------- Принятие / отклонение ----------

def accept_invitation(
    db: Session,
    token: str,
    user: User,
) -> tuple[Invitation, CohortMember]:
    """
    Принимает приглашение.

    Проверки:
    - invitation существует, status=pending, не истекло;
    - user.email == invitation.email;
    - user.role == GUEST (не студент, не ментор);
    - когорта не переполнена.

    Эффекты:
    - invitation.status = accepted, accepted_at = now;
    - user.role = STUDENT;
    - создаётся CohortMember.
    """
    invitation = invitation_crud.get_invitation_by_token(db, token)
    if invitation is None:
        raise InvitationNotFoundError("Invitation not found")

    invitation = _mark_expired_if_needed(db, invitation)

    if invitation.status == InvitationStatus.EXPIRED:
        raise InvitationExpiredError("Invitation has expired")

    if invitation.status != InvitationStatus.PENDING:
        raise InvitationAlreadyUsedError(
            f"Invitation is already {invitation.status.value}"
        )

    # Email совпадает?
    if user.email.lower() != invitation.email.lower():
        raise InvitationError(
            "Invitation email does not match your account email"
        )

    if user.role == UserRole.STUDENT:
        raise UserAlreadyStudentError("You are already a student")

    if user.role in (UserRole.MENTOR, UserRole.ADMIN):
        raise InvitationError("Mentors and admins cannot accept invitations")

    # Когорта не переполнена?
    students_count = cohort_crud.count_students(db, invitation.cohort_id)
    if students_count >= MAX_STUDENTS_PER_COHORT:
        raise CohortFullError(
            f"Cohort is full ({students_count}/{MAX_STUDENTS_PER_COHORT})"
        )

    # Меняем статус приглашения
    invitation = invitation_crud.update_status(
        db, invitation, InvitationStatus.ACCEPTED
    )

    # Меняем роль пользователя
    user.role = UserRole.STUDENT
    db.add(user)
    db.commit()
    db.refresh(user)

    # Добавляем в когорту
    member = cohort_crud.add_member(
        db,
        cohort_id=invitation.cohort_id,
        user_id=user.id,
        role=CohortRole.STUDENT,
    )

    return invitation, member


def decline_invitation(
    db: Session,
    token: str,
    user: User,
) -> Invitation:
    """
    Отклоняет приглашение.

    Доступно только пользователю с подходящим email.
    """
    invitation = invitation_crud.get_invitation_by_token(db, token)
    if invitation is None:
        raise InvitationNotFoundError("Invitation not found")

    invitation = _mark_expired_if_needed(db, invitation)

    if invitation.status != InvitationStatus.PENDING:
        raise InvitationAlreadyUsedError(
            f"Invitation is already {invitation.status.value}"
        )

    if user.email.lower() != invitation.email.lower():
        raise InvitationError(
            "Invitation email does not match your account email"
        )

    return invitation_crud.update_status(
        db, invitation, InvitationStatus.DECLINED
    )
