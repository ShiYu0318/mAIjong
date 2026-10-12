"""player progression and guest accounts

Revision ID: 5f2c9d1e7a40
Revises: 38a1b0c604cc
Create Date: 2026-10-13 00:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5f2c9d1e7a40'
down_revision: Union[str, Sequence[str], None] = '38a1b0c604cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('is_guest', sa.Boolean(), nullable=False,
                                   server_default=sa.false()))
    op.create_table('user_progress',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('xp', sa.Integer(), nullable=False),
    sa.Column('coins', sa.Integer(), nullable=False),
    sa.Column('bonus_day', sa.String(length=10), nullable=True),
    sa.Column('bonus_streak', sa.Integer(), nullable=False),
    sa.Column('missions_day', sa.String(length=10), nullable=True),
    sa.Column('missions', sa.JSON(), nullable=False),
    sa.Column('achievements', sa.JSON(), nullable=False),
    sa.Column('owned', sa.JSON(), nullable=False),
    sa.Column('equipped', sa.JSON(), nullable=False),
    sa.Column('stats', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('user_progress')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('is_guest')
