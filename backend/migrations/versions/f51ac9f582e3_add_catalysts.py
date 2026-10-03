"""add catalysts

events (PDUFA dates, AdComs, readouts, ...) extracted from sec_filings by the llm.

Revision ID: f51ac9f582e3
Revises: 31b99dc785b4
Create Date: 2026-10-03 20:39:12.470082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f51ac9f582e3'
down_revision: Union[str, None] = '31b99dc785b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'catalysts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('accession_number', sa.String(length=25), nullable=False),
        sa.Column('filing_url', sa.String(length=500), nullable=False),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('drug', sa.String(length=200), nullable=True),
        sa.Column('indication', sa.String(length=300), nullable=True),
        sa.Column('date_text', sa.String(length=100), nullable=True),
        sa.Column('event_date', sa.Date(), nullable=True),
        sa.Column('date_precision', sa.String(length=10), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('source_quote', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['accession_number'], ['sec_filings.accession_number'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_catalysts_ticker', 'catalysts', ['ticker'])
    op.create_index('ix_catalysts_accession_number', 'catalysts', ['accession_number'])


def downgrade() -> None:
    op.drop_index('ix_catalysts_accession_number', table_name='catalysts')
    op.drop_index('ix_catalysts_ticker', table_name='catalysts')
    op.drop_table('catalysts')
