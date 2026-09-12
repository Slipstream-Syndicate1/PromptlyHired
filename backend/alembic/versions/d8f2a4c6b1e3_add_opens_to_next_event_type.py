"""add 'opens' to next_event_type enum

Revision ID: d8f2a4c6b1e3
Revises: c7d4b1f8e2a9
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8f2a4c6b1e3'
down_revision: Union[str, None] = 'c7d4b1f8e2a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres 12+ allows ADD VALUE inside a transaction as long as the new
    # value isn't used in that same transaction, which it isn't here.
    op.execute("ALTER TYPE next_event_type ADD VALUE IF NOT EXISTS 'opens'")


def downgrade() -> None:
    # Postgres has no DROP VALUE - recreate the type without it. Any rows
    # using it fall back to 'other' rather than becoming invalid.
    op.execute("UPDATE user_jobs SET next_event_type = 'other' WHERE next_event_type = 'opens'")
    op.execute("ALTER TYPE next_event_type RENAME TO next_event_type_old")
    sa.Enum('interview', 'deadline', 'other', name='next_event_type').create(op.get_bind())
    op.execute(
        "ALTER TABLE user_jobs ALTER COLUMN next_event_type "
        "TYPE next_event_type USING next_event_type::text::next_event_type"
    )
    op.execute("DROP TYPE next_event_type_old")
