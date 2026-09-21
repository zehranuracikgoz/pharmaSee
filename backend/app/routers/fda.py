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
from sqlalchemy import select

router = APIRouter(prefix="/fda", tags=["FDA"])

@router.get("/calendar", response_model=FDACalendarOut, summary="Yaklaşan FDA kararları takvimi")
async def fda_calendar(
    days_ahead: int = Query(default=90, ge=1, le=365, description="Kaç gün ilerisi"),
    db: AsyncSession = Depends(get_db),
):
    """
    önümüzdeki `days_ahead` gün içindeki FDA onay kararlarini listelemek icin
    onbellek 24 saat
    """
    return await get_fda_calendar(db, days_ahead=days_ahead)


@router.get("/{ticker}/approvals", response_model=list[DrugApprovalOut], summary="Şirket FDA onayları")
async def company_approvals(
    ticker: str,
    db: AsyncSession =Depends(get_db),
):
    """
    Belirli bir biyoteknoloji şirketinin FDA onay gecmisini listelemek icin.
    ilk cagrida OpenFDA'dan ceker, sonraki çağrılarda onbellekten servis eder.
    """
    ticker = ticker.upper()
    await upsert_approvals(ticker, db)
    stmt = select(DrugApproval).where(DrugApproval.company_id == ticker).order_by(
        DrugApproval.approval_date.desc()
    )
    result =await db.execute(stmt)
    return result.scalars().all()


@router.get("/{ticker}/trials", summary="Aktif klinik araştırmalar")
async def clinical_trials(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    ClinicalTrials.gov dan şirketin aktif klinik araştırmalarını listelemek için
    """
    ticker = ticker.upper()
    return await fetch_clinical_trials(ticker, db)


@router.post("/sync", summary="Şirket listesini senkronize et")
async def sync(db: AsyncSession = Depends(get_db)):
    """
    BIOTECH_TICKERS listesindeki tüm şirketleri veritabanına ekliyor
    Geliştirme/demo icin.
    """
    await sync_companies(db)
    return {"status": "ok","message": "Şirketler senkronize edildi"}