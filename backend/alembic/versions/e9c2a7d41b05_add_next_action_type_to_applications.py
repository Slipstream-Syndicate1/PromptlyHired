"""add next_action_type to applications

Revision ID: e9c2a7d41b05
Revises: 6748afe89a48
Create Date: 2026-09-12 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e9c2a7d41b05'
down_revision: Union[str, None] = '6748afe89a48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # What kind of thing next_action / next_action_date describe, so the
    # tracking board and calendar can colour-code it. A plain string rather
    # than a Postgres enum: the set is small, UI-driven, and validated at the
    # API boundary, and a string column needs no ALTER TYPE to extend later.
    op.add_column(
        'applications',
        sa.Column('next_action_type', sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('applications', 'next_action_type')
