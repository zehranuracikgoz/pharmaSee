"""
OpenFDA API + ClinicalTrials.gov API entegrasyonu

OpenFDA  → https://api.fda.gov/drug/drugsfda.json
ClinTrials → https://clinicaltrials.gov/api/v2/studies
"""
import uuid
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Company, DrugApproval
from app.schemas.schemas import FDACalendarItem, FDACalendarOut
from app.services.cache_service import get_cached, set_cached

OPENFDA_BASE = "https://api.fda.gov/drug/drugsfda.json"
CLINTRIALS_BASE = "https://clinicaltrials.gov/api/v2/studies"

# biyoteknoloji / ilaç izleme listesi — genislyebilir
BIOTECH_TICKERS = {
    "MRNA": "Moderna",
    "BNTX": "BioNTech",
    "PFE": "Pfizer",
    "REGN": "Regeneron",
    "BIIB": "Biogen",
    "GILD": "Gilead Sciences",
    "AMGN": "Amgen",
    "VRTX": "Vertex Pharmaceuticals",
    "SGEN": "Seagen",
    "BLUE": "bluebird bio",
    "BEAM": "Beam Therapeutics",
    "CRSP": "CRISPR Therapeutics",
    "NTLA": "Intellia Therapeutics",
}


async def _fetch_json(url: str, params: dict, timeout: float = 15.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def sync_companies(db: AsyncSession) -> None:
    """BIOTECH_TICKERS listesindeki şirketleri veritabanına kaydetmek (yoksa eklemek) icin"""
    for ticker, name in BIOTECH_TICKERS.items():
        existing =await db.get(Company, ticker)
        if not existing:
            db.add(Company(ticker=ticker, name=name, sector="Biotechnology"))
    await db.commit()

async def fetch_fda_approvals_for_company(
    ticker:str, company_name: str, db: AsyncSession
) -> list[dict]:
    """
    OpenFDA dan belirli şirket için onay kayıtlarını çek
    önbellekte varsa döndür.
    """
    cache_key = "fda_approvals"
    params = {"ticker": ticker}

    cached =await get_cached(db, cache_key, params)
    if cached:
        return cached

    search_term = company_name.split()[0].lower()
    try:
        data = await _fetch_json(
            OPENFDA_BASE,
            {
                "search": f'openfda.manufacturer_name:"{search_term}"',
                "limit": 50,
            },
        )
        results =data.get("results", [])
    except (httpx.HTTPError, Exception):
        results = []

    approvals = []
    for r in results:
        submissions = r.get("submissions", [])
        for sub in submissions:
            if sub.get("submission_type") in ("ORIG", "SUPPL"):
                approval_date_str = sub.get("submission_status_date", "")
                try:
                    approval_date = datetime.strptime(
                        approval_date_str [:8], "%Y%m%d"
                    ).date() if approval_date_str else None
                except ValueError:
                    approval_date = None

                brand = r.get("openfda", {}).get("brand_name", [""])[0]
                generic = r.get("openfda", {}).get("generic_name", [""])[0]
                app_type = r.get("application_number", "")[:3]  # NDA / BLA

                approvals.append(
                    {
                        "id": str(uuid.uuid4()),
                        "company_id": ticker,
                        "drug_name": generic or brand or "Bilinmiyor",
                        "brand_name": brand,
                        "approval_date": str(approval_date) if approval_date else None,
                        "application_type": app_type,
                        "status":"Approved"
                        if sub.get("submission_status") == "AP"
                        else sub.get("submission_status"),
                        "indication": None,
                    }
                )

    await set_cached(db, cache_key, params, approvals)
    return approvals

async def upsert_approvals(ticker: str, db: AsyncSession) -> list[DrugApproval]:
    """Şirket için API den çekilen onayları DB'ye yaz, listeyi döndür."""
    company = await db.get(Company, ticker)
    if not company:
        return []

    raw = await fetch_fda_approvals_for_company(ticker, company.name, db)

    records = []
    for a in raw:
        existing = await db.get(DrugApproval, a["id"])
        if not existing:
            obj = DrugApproval(
                id=a["id"],
                company_id=ticker,
                drug_name=a["drug_name"],
                brand_name=a["brand_name"],
                approval_date=date.fromisoformat(a["approval_date"])
                if a["approval_date"]
                else None,
                application_type=a["application_type"],
                status=a["status"],
            )
            db.add(obj)
            records.append(obj)
        else:
            records.append(existing)

    await db.commit()
    return records

async def get_fda_calendar(
    db: AsyncSession,
    days_ahead: int = 90,
) -> FDACalendarOut:
    """
    `days_ahead` gün içindeki FDA kararlarını döndür
    önce DB'yi kontrol et; yoksa OpenFDA'yı çek.
    """
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    stmt = select(DrugApproval).where(
        DrugApproval.approval_date >= today,
        DrugApproval.approval_date <= cutoff,
        DrugApproval.status == "Pending",
    )
    result = await db.execute(stmt)
    pending = result.scalars().all()

    # DB de yeterli pending kayıt yoksa tüm şirketleri senkronize etmek icin
    if len(pending) < 3:
        await sync_companies(db)
        for ticker in list(BIOTECH_TICKERS.keys())[:5]:
            await upsert_approvals(ticker, db)
        result = await db.execute(stmt)
        pending = result.scalars().all()

    # Şirket adlarını çek
    company_map: dict[str, str] = {}
    company_result =await db.execute(select(Company))
    for c in company_result.scalars().all():
        company_map[c.ticker] = c.name

    items = [
        FDACalendarItem(
            company_name=company_map.get(a.company_id, a.company_id),
            ticker=a.company_id,
            drug_name=a.drug_name,
            brand_name=a.brand_name,
            pdufa_date=a.approval_date,
            application_type=a.application_type,
            status=a.status,
        )
        for a in pending
    ]

    return FDACalendarOut(items=items, total=len(items))

async def fetch_clinical_trials(ticker: str, db: AsyncSession) -> list[dict]:
    """ClinicalTrials.gov'dan şirket adına göre aktif trialları çek."""
    cache_key = "clinical_trials"
    params = {"ticker": ticker}

    cached =await get_cached(db, cache_key, params)
    if cached:
        return cached

    company = await db.get(Company, ticker)
    if not company:
        return []

    sponsor = company.name.split()[0]
    try:
        data = await _fetch_json(
            CLINTRIALS_BASE,
            {
                "query.spons" : sponsor,
                "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING",
                "pageSize": 20,
                "format": "json",
            },
        )
        studies = data.get("studies", [])
    except (httpx.HTTPError, Exception):
        studies = []

    trials = []
    for s in studies:
        proto=s.get("protocolSection", {})
        id_info = proto.get("identificationModule", {})
        status_info = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        conditions = proto.get("conditionsModule" , {})

        phase_list = design.get("phases", [])
        phase = phase_list[0] if phase_list else "N/A"

        trials.append(
            {
                "nct_id" : id_info.get("nctId", ""),
                "title": id_info.get("briefTitle", ""),
                "phase": phase,
                "status": status_info.get("overallStatus", ""),
                "conditions": conditions.get("conditions", []),
            }
        )

    await set_cached(db, cache_key, params, trials)
    return trials
