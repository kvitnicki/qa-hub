"""migrate user roles to platform roles

Revision ID: 546d1d26f9c1
Revises: f3fefea6e505
Create Date: 2026-10-13 15:23:56.188227

Миграция преобразует старые роли (qa_lead, tester, viewer) в новые
(mentor, student), а также обновляет CheckConstraint на таблице users.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '546d1d26f9c1'
down_revision: Union[str, None] = 'f3fefea6e505'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Убираем старый CheckConstraint
    op.drop_constraint('ck_users_role_valid', 'users', type_='check')

    # 2. Преобразуем данные:
    #    qa_lead → mentor (владельцы проектов становятся менторами)
    #    tester, viewer → student (обычные пользователи становятся студентами)
    op.execute("UPDATE users SET role='mentor' WHERE role='qa_lead'")
    op.execute("UPDATE users SET role='student' WHERE role IN ('tester', 'viewer')")

    # 3. Добавляем новый CheckConstraint
    op.create_check_constraint(
        'ck_users_role_valid',
        'users',
        "role IN ('admin', 'mentor', 'student', 'guest')",
    )


def downgrade() -> None:
    # Обратная миграция
    op.drop_constraint('ck_users_role_valid', 'users', type_='check')

    op.execute("UPDATE users SET role='qa_lead' WHERE role='mentor'")
    op.execute("UPDATE users SET role='tester' WHERE role='student'")
    op.execute("UPDATE users SET role='tester' WHERE role='guest'")

    op.create_check_constraint(
        'ck_users_role_valid',
        'users',
        "role IN ('admin', 'qa_lead', 'tester', 'viewer')",
    )
