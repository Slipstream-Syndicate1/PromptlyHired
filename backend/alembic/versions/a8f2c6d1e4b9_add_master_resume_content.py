"""add master resume content

Revision ID: a8f2c6d1e4b9
Revises: 6748afe89a48
Create Date: 2026-09-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a8f2c6d1e4b9"
down_revision: Union[str, None] = "6748afe89a48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("master_content", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("resumes", "master_content")
