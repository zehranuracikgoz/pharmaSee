"""clear placeholder company sectors

sync_companies used to write sector "Biotechnology" for every company. yfinance never
returns that as a sector (it's an industry under "Healthcare"), so it's always a
placeholder — set it to null until .info provides a real one.

Revision ID: 626671fc7c86
Revises: 364e3258bc07
Create Date: 2026-10-03 19:55:04.651278

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '626671fc7c86'
down_revision: Union[str, None] = '364e3258bc07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

companies = sa.table("companies", sa.column("sector", sa.String))


def upgrade() -> None:
    op.execute(
        sa.update(companies)
        .where(companies.c.sector == "Biotechnology")
        .values(sector=None)
    )


def downgrade() -> None:
    # placeholders were never real data; nothing to restore
    pass
