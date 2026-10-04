"""add company industry

yfinance industry per company (e.g. "Biotechnology"), filled when .info works. the api
falls back to the static TRACKED_INDUSTRIES mapping when it is null.

Revision ID: b7d1f3a9c2e4
Revises: 9c2e4b7a1d35
Create Date: 2026-10-04 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d1f3a9c2e4'
down_revision: Union[str, None] = '9c2e4b7a1d35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('industry', sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('companies') as batch:  # sqlite can't drop columns without batch mode
        batch.drop_column('industry')
