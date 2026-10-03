from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.models import SecFiling
from app.security import require_admin
from app.services.catalyst_service import is_running, process_pending_filings
from app.services.sec_service import sync_sec_filings

router = APIRouter(prefix="/sec", tags=["SEC"])


@router.post("/sync", summary="Fetch recent SEC filings", dependencies=[Depends(require_admin)])
async def sync(db: AsyncSession = Depends(get_db)):
    """
    Store recent 8-K (items 7.01 / 8.01) and 6-K filings for every tracked company.
    Already stored filings are skipped. Can take a minute or two.
    """
    summary= await sync_sec_filings(db)
    if summary["error"]:
        raise HTTPException(status_code=503, detail=summary["error"])
    return {"status": "ok", **{k: v for k, v in summary.items() if k != "error"}}


@router.post(
    "/extract",
    status_code=202,
    summary="Extract catalysts from stored filings",
    dependencies=[Depends(require_admin)],
)
async def extract(background: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Start catalyst extraction (llm) for unprocessed filings in the background — a run
    can take several minutes because of free-tier rate limits. Results show up in
    GET /catalysts; the run summary goes to the server log.
    """
    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not set")
    if is_running():
        raise HTTPException(status_code=409, detail="extraction is already running")
    pending = await db.scalar(
        select(func.count()).select_from(SecFiling).where(SecFiling.processed.is_(False))
    )
    background.add_task(process_pending_filings)    #opens its own db session
    return {"status": "started", "pending_filings": pending}