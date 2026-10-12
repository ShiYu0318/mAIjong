"""replay verification flag on games

Revision ID: 9c41e2b7d5a3
Revises: 5f2c9d1e7a40
Create Date: 2026-10-13 06:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c41e2b7d5a3'
down_revision: Union[str, Sequence[str], None] = '5f2c9d1e7a40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('games') as batch:
        batch.add_column(sa.Column('replay_verified', sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('games') as batch:
        batch.drop_column('replay_verified')
