"""merge recommendations and master resume

Revision ID: 08fd1a1ed7a0
Revises: 8eba1b630d8b, a8f2c6d1e4b9
Create Date: 2026-09-12 21:58:24.782265

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '08fd1a1ed7a0'
down_revision: Union[str, None] = ('8eba1b630d8b', 'a8f2c6d1e4b9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
