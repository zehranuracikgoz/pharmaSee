"""prefix approval ids with ticker

ids change from "{app_number}-{type}-{num}" to "{ticker}-{app_number}-{type}-{num}",
so co-marketed drugs get a separate row per company instead of colliding.

Revision ID: 364e3258bc07
Revises: c37c8ad6adbc
Create Date: 2026-10-03 11:58:59.091862

"""
import logging
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '364e3258bc07'
down_revision: Union[str, None] = 'c37c8ad6adbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")

# ticker-less id, e.g. "BLA761339-ORIG-1" or "NDA021234-SUPPL-45"
OLD_ID = re.compile(r"^[A-Z]+\d+-[A-Z]+-[^-]+$")

drug_approvals=sa.table(
    "drug_approvals",
    sa.column("id", sa.String),
    sa.column("company_id", sa.String),
)
cache_entries = sa.table("cache_entries", sa.column("endpoint", sa.String))


def _has_ticker_prefix(approval_id: str, ticker: str) -> bool:
    prefix = f"{ticker}-"
    return approval_id.startswith(prefix) and bool(OLD_ID.match(approval_id[len(prefix):]))


def _drop_cached_approvals(conn, endpoints: list[str]) -> None:
# old cache holds ids in the previous format — drop so they're re-fetched clean
    conn.execute(sa.delete(cache_entries).where(cache_entries.c.endpoint.in_(endpoints)))


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.select(drug_approvals.c.id, drug_approvals.c.company_id)).all()
    taken = {r.id for r in rows}
    renamed = skipped = removed = 0

    for approval_id, ticker in rows:
        if _has_ticker_prefix(approval_id, ticker):
            skipped += 1  #already migrated, safe to re-run
            continue

        if OLD_ID.match(approval_id):
            new_id = f"{ticker}-{approval_id}"
            if new_id in taken:
# new-format row exists; old one is a duplicate
                conn.execute(sa.delete(drug_approvals).where(drug_approvals.c.id == approval_id))
                removed += 1
            else:
                conn.execute(
                    sa.update(drug_approvals)
                    .where(drug_approvals.c.id == approval_id)
                    .values(id=new_id)
                )
                taken.add(new_id)
                renamed += 1
        else:
# legacy uuid ids can't be rebuilt — drop them so re-fetch creates clean rows
            conn.execute(sa.delete(drug_approvals).where(drug_approvals.c.id == approval_id))
            removed += 1
        taken.discard(approval_id)

    _drop_cached_approvals(conn, ["fda_approvals", "fda_approvals_v2"])
    log.info("drug_approvals: %d renamed, %d already prefixed, %d removed", renamed, skipped, removed)


def downgrade() -> None:
    conn=op.get_bind()
    rows=conn.execute(sa.select(drug_approvals.c.id, drug_approvals.c.company_id)).all()
    taken = {r.id for r in rows}

    for approval_id, ticker in rows:
        if not _has_ticker_prefix(approval_id, ticker):
            continue
        old_id = approval_id[len(ticker) + 1:]
        if old_id in taken:
# old format can't hold one row per company for shared applications
            conn.execute(sa.delete(drug_approvals).where(drug_approvals.c.id == approval_id))
        else:
            conn.execute(
                sa.update(drug_approvals)
                .where(drug_approvals.c.id == approval_id)
                .values(id=old_id)
            )
            taken.add(old_id)
        taken.discard(approval_id)

    _drop_cached_approvals(conn, ["fda_approvals_v3"])