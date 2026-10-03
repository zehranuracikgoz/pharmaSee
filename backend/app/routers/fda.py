from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.schemas import DrugApprovalOut, FDACalendarOut
from app.services.fda_service import (
    fetch_clinical_trials,
    get_fda_calendar,
    sync_companies,
    upsert_approvals,
)
from app.models.models import DrugApproval
from app.security import require_admin
from sqlalchemy import select

router = APIRouter(prefix="/fda", tags=["FDA"])

@router.get("/calendar", response_model=FDACalendarOut, summary="Upcoming FDA decisions calendar")
async def fda_calendar(
    days_ahead: int = Query(default=90, ge=1, le=365, description="Number of days ahead"),
    db: AsyncSession = Depends(get_db),
):
    """
    List FDA approval decisions within the next `days_ahead` days.
    Cached for 24 hours.
    """
    return await get_fda_calendar(db, days_ahead=days_ahead)


@router.get("/{ticker}/approvals", response_model=list[DrugApprovalOut], summary="Company FDA approvals")
async def company_approvals(
    ticker: str,
    db: AsyncSession =Depends(get_db),
):
    """
    List the FDA approval history of a biotech company.
    Fetched from OpenFDA on the first call, served from cache afterwards.
    """
    ticker = ticker.upper()
    await upsert_approvals(ticker, db)
    stmt = select(DrugApproval).where(DrugApproval.company_id == ticker).order_by(
        DrugApproval.approval_date.desc()
    )
    result =await db.execute(stmt)
    return result.scalars().all()


@router.get("/{ticker}/trials", summary="Active clinical trials")
async def clinical_trials(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List the company's active clinical trials from ClinicalTrials.gov.
    """
    ticker = ticker.upper()
    return await fetch_clinical_trials(ticker, db)


@router.post("/sync", summary="Sync the company list", dependencies=[Depends(require_admin)])
async def sync(db: AsyncSession = Depends(get_db)):
    """
    Insert every company from TRACKED_TICKERS into the database.
    For development/demo use.
    """
    await sync_companies(db)
    return {"status": "ok","message": "Companies synced"}