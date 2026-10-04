from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Catalyst, SecFiling
from app.security import require_admin
from app.services.catalyst_service import is_running, process_pending_filings
from app.services.llm_service import enabled_providers, missing_key_message
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
    Start catalyst extraction (every enabled llm) for unprocessed filings in the background — a run
    can take several minutes because of free-tier rate limits. Results show up in
    GET /catalysts; the run summary goes to the server log.
    """
    if not enabled_providers():
        raise HTTPException(status_code=503, detail=missing_key_message())
    if is_running():
        raise HTTPException(status_code=409, detail="extraction is already running")
    pending = await db.scalar(
        select(func.count()).select_from(SecFiling).where(SecFiling.processed.is_(False))
    )
    background.add_task(process_pending_filings)    #opens its own db session
    return {"status": "started", "pending_filings": pending}


@router.post(
    "/reextract",
    status_code=202,
    summary="Re-extract catalysts from all stored filings",
    dependencies=[Depends(require_admin)],
)
async def reextract(background: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Delete all catalysts, mark every stored filing as unprocessed and start a normal
    extraction run in the background. Same rate limits as /sec/extract: one run handles
    at most 40 filings, so call /sec/extract again for the rest.
    """
    if not enabled_providers():
        raise HTTPException(status_code=503, detail=missing_key_message())
    if is_running():
        raise HTTPException(status_code=409, detail="extraction is already running")
    deleted = (await db.execute(delete(Catalyst))).rowcount
    pending = (await db.execute(update(SecFiling).values(processed=False))).rowcount
    await db.commit()
    background.add_task(process_pending_filings)
    return {"status": "started", "catalysts_deleted": deleted, "pending_filings": pending}