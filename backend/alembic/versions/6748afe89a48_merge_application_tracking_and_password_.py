"""merge application tracking and password reset migrations

Revision ID: 6748afe89a48
Revises: 78d424116366, b7e4c1d9a2f3
Create Date: 2026-09-12 15:15:47.997032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6748afe89a48'
down_revision: Union[str, None] = ('78d424116366', 'b7e4c1d9a2f3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
