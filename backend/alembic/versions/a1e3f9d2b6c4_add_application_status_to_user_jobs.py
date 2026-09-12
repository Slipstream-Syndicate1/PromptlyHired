"""add application status tracking to user_jobs

Revision ID: a1e3f9d2b6c4
Revises: 524a1fa660af
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1e3f9d2b6c4'
down_revision: Union[str, None] = '524a1fa660af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


application_status = sa.Enum(
    'applied', 'interview', 'offer', 'rejected', name='application_status'
)


def upgrade() -> None:
    application_status.create(op.get_bind(), checkfirst=True)
    op.add_column('user_jobs', sa.Column('status', application_status, nullable=True))
    op.add_column(
        'user_jobs', sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'user_jobs', sa.Column('status_updated_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(op.f('ix_user_jobs_status'), 'user_jobs', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_jobs_status'), table_name='user_jobs')
    op.drop_column('user_jobs', 'status_updated_at')
    op.drop_column('user_jobs', 'applied_at')
    op.drop_column('user_jobs', 'status')
    application_status.drop(op.get_bind(), checkfirst=True)
