"""add catalyst votes

cross-model voting: votes, models_total and agreed_by on catalysts.
existing rows were extracted by gemini alone: 1/1, "gemini".

Revision ID: 9c2e4b7a1d35
Revises: f51ac9f582e3
Create Date: 2026-10-04 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c2e4b7a1d35'
down_revision: Union[str, None] = 'f51ac9f582e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('catalysts', sa.Column('votes', sa.Integer(), server_default='1', nullable=False))
    op.add_column('catalysts', sa.Column('models_total', sa.Integer(), server_default='1', nullable=False))
    op.add_column(
        'catalysts', sa.Column('agreed_by', sa.String(length=100), server_default='gemini', nullable=False)
    )


def downgrade() -> None:
    with op.batch_alter_table('catalysts') as batch:  # sqlite can't drop columns without batch mode
        batch.drop_column('agreed_by')
        batch.drop_column('models_total')
        batch.drop_column('votes')
