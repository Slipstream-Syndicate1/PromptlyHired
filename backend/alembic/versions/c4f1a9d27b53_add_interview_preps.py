"""add interview preps

Revision ID: c4f1a9d27b53
Revises: 08fd1a1ed7a0
Create Date: 2026-09-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4f1a9d27b53"
down_revision: Union[str, None] = "08fd1a1ed7a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_preps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("model_used", sa.String(length=60), nullable=True),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # One plan per application: asking again replaces it rather than piling up.
    op.create_index(
        "ix_interview_preps_application_id", "interview_preps", ["application_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_interview_preps_application_id", table_name="interview_preps")
    op.drop_table("interview_preps")
