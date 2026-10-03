from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Catalyst
from app.schemas.schemas import CatalystOut
from app.services.catalyst_service import EVENT_TYPES, period_end

router = APIRouter(tags=["Catalysts"])


@router.get("/catalysts", response_model=list[CatalystOut], summary="Catalysts from SEC filings")
async def list_catalysts(
    upcoming: bool = Query(default=False, description="Only events that haven't passed yet"),
    past_days: int | None = Query(
        default=None, ge=1, le=730, description="Only events that ended within the last N days"
    ),
    ticker: str | None = Query(default=None, description="Filter by ticker"),
    event_type: str | None = Query(default=None, description=f"One of: {', '.join(EVENT_TYPES)}"),
    db: AsyncSession = Depends(get_db),
):
    """
    Catalysts extracted from SEC filings, sorted by event date (undated ones last).
    upcoming=true keeps events whose period hasn't ended: "Q4 2026" is stored as
    2026-10-01 but still counts as upcoming until December 31.
    past_days=N returns events that already ended in the last N days, newest first.
    """
    stmt = select(Catalyst)
    if ticker:
        stmt =stmt.where(Catalyst.ticker == ticker.upper())
    if event_type:
        stmt = stmt.where(Catalyst.event_type == event_type)
    rows = (await db.scalars(stmt)).all()

    today = date.today()
    if upcoming:
        rows = [r for r in rows if r.event_date and period_end(r.event_date, r.date_precision) >= today]
    if past_days:
        since =today - timedelta(days=past_days)
        rows = [r for r in rows if r.event_date and since <= r.event_date
                and period_end(r.event_date, r.date_precision) < today]
        return sorted(rows, key=lambda r: (r.event_date, r.ticker), reverse=True)
    return sorted(rows, key=lambda r: (r.event_date is None, r.event_date or date.max, r.ticker))