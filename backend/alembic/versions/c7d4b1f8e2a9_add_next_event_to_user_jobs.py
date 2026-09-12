"""add next event (interview/deadline/reminder) to user_jobs

Revision ID: c7d4b1f8e2a9
Revises: a1e3f9d2b6c4
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d4b1f8e2a9'
down_revision: Union[str, None] = 'a1e3f9d2b6c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


next_event_type = sa.Enum('interview', 'deadline', 'other', name='next_event_type')


def upgrade() -> None:
    next_event_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'user_jobs', sa.Column('next_event_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('user_jobs', sa.Column('next_event_type', next_event_type, nullable=True))
    op.add_column(
        'user_jobs', sa.Column('next_event_note', sa.String(length=300), nullable=True)
    )
    op.create_index(
        op.f('ix_user_jobs_next_event_at'), 'user_jobs', ['next_event_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_user_jobs_next_event_at'), table_name='user_jobs')
    op.drop_column('user_jobs', 'next_event_note')
    op.drop_column('user_jobs', 'next_event_type')
    op.drop_column('user_jobs', 'next_event_at')
    next_event_type.drop(op.get_bind(), checkfirst=True)
