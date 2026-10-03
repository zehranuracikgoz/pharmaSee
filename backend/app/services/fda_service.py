"""
OpenFDA API + ClinicalTrials.gov API integration

OpenFDA  → https://api.fda.gov/drug/drugsfda.json
ClinTrials → https://clinicaltrials.gov/api/v2/studies
"""
import logging
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.models import Company, DrugApproval
from app.schemas.schemas import FDACalendarItem, FDACalendarOut
from app.services.catalyst_service import process_pending_filings
from app.services.sec_service import sync_sec_filings
from app.services.stock_service import refresh_market_caps
from app.services.cache_service import (
    get_cached,
    invalidate_cached,
    purge_expired,
    set_cached,
)

logger = logging.getLogger(__name__)

OPENFDA_BASE = "https://api.fda.gov/drug/drugsfda.json"
CLINTRIALS_BASE = "https://clinicaltrials.gov/api/v2/studies"
# one page only; companies with more active trials show as "100+" in the UI
TRIALS_PAGE_SIZE = 100

# v3: ids include the ticker; cached v2 lists hold ticker-less ids and must not be reused
_APPROVALS_CACHE_KEY = "fda_approvals_v3"


async def _fetch_json(url: str, params: dict, timeout: float = 15.0) -> dict:
    """
    Return the JSON of a successful response. OpenFDA reports "no matches" as a 404 —
    that is a valid empty result, so {} is returned. Other HTTP / network errors are raised.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, params=params)
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return resp.json()


def _is_meaningful_submission(sub: dict) -> bool:
    """Original approvals + new-indication (EFFICACY) supplements; drops labeling / CMC changes."""
    sub_type = sub.get("submission_type") or ""
    return sub_type == "ORIG" or (
        sub_type.startswith("SUPPL") and sub.get("submission_class_code") == "EFFICACY"
    )


def parse_approvals(ticker: str, results: list[dict]) -> list[dict]:
    """Convert OpenFDA drugsfda results into DrugApproval rows (deduplicated)."""
    approvals: dict[str, dict] = {}
    for r in results:
        application_number = r.get("application_number", "")
        openfda = r.get("openfda", {})
        brand = (openfda.get("brand_name") or [""])[0]
        generic = (openfda.get("generic_name") or [""])[0]
        app_type = "".join(ch for ch in application_number if ch.isalpha())  # NDA / BLA / ANDA

        for sub in r.get("submissions", []):
            if not _is_meaningful_submission(sub):
                continue

            approval_date_str = sub.get("submission_status_date", "")
            try:
                approval_date = datetime.strptime(
                    approval_date_str [:8], "%Y%m%d"
                ).date() if approval_date_str else None
            except ValueError:
                approval_date = None

            # ticker first: co-marketed drugs (pfizer/biontech) share an
            # application, and each company needs its own row
            approval_id = (
                f"{ticker}-{application_number}-"
                f"{sub.get('submission_type')}-{sub.get('submission_number')}"
            )
            approvals[approval_id] = {
                "id": approval_id,
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
    return list(approvals.values())


async def sync_companies(db: AsyncSession) -> None:
    """Insert companies from TRACKED_TICKERS into the DB if missing."""
    for ticker, name in settings.TRACKED_TICKERS.items():
        existing =await db.get(Company, ticker)
        if not existing:
            # sector stays null until yfinance provides a real one
            db.add(Company(ticker=ticker, name=name))
    await db.commit()

async def fetch_fda_approvals_for_company(
    ticker:str, company_name: str, db: AsyncSession
) -> list[dict]:
    """
    Fetch approval records for a company from OpenFDA;
    return the cached copy if present.
    """
    cache_key = _APPROVALS_CACHE_KEY
    params = {"ticker": ticker}

    cached =await get_cached(db, cache_key, params)
    if cached is not None:
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
    except (httpx.HTTPError, ValueError):
        # failed requests aren't cached; the next call retries
        logger.exception("OpenFDA request failed for %s", ticker)
        return []

    approvals = parse_approvals(ticker, data.get("results", []))
    await set_cached(db, cache_key, params, approvals)
    return approvals


def _insert_ignore(db: AsyncSession):
    """INSERT ... ON CONFLICT DO NOTHING for the current dialect (SQLite: same as INSERT OR IGNORE)."""
    dialect = db.get_bind().dialect.name
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert
    return insert_fn(DrugApproval).on_conflict_do_nothing(index_elements=["id"])


async def upsert_approvals(ticker: str, db: AsyncSession) -> list[DrugApproval]:
    """Write fetched approvals to the DB (skipping existing ones) and return the company's rows."""
    company = await db.get(Company, ticker)
    if not company:
        return []

    raw = await fetch_fda_approvals_for_company(ticker, company.name, db)

    if raw:
        rows = [
            {
                "id": a["id"],
                "company_id": ticker,
                "drug_name": a["drug_name"],
                "brand_name": a["brand_name"],
                "approval_date": date.fromisoformat(a["approval_date"])
                if a["approval_date"]
                else None,
                "application_type": a["application_type"],
                "status": a["status"],
            }
            for a in raw
        ]
        await db.execute(_insert_ignore(db), rows)
        await db.commit()

    result = await db.execute(
        select(DrugApproval).where(DrugApproval.company_id == ticker)
    )
    return list(result.scalars().all())

async def run_scheduled_sync() -> None:
    """daily sync: company list, fresh approvals, market caps, sec filings and catalyst extraction"""
    async with AsyncSessionLocal() as db:
        await sync_companies(db)
        refreshed = 0
        for ticker in settings.TRACKED_TICKERS:
            try:
                await invalidate_cached(db, _APPROVALS_CACHE_KEY, {"ticker": ticker})
                await upsert_approvals(ticker, db)
                refreshed+= 1
            except Exception:
                logger.exception("Scheduled FDA sync failed for %s", ticker)
        caps_updated, caps_no_data, caps_failed = await refresh_market_caps(db)
        sec = await sync_sec_filings(db)
        extraction = await process_pending_filings(db)
        purged=await purge_expired(db)
    logger.info(
        "scheduled sync done: approvals %d/%d refreshed | market caps %d updated, "
        "%d no data, %d failed | sec filings %d new, %d failed | catalysts %d saved from "
        "%d filings (%d prefiltered, %d failed%s) | %d expired cache entries purged",
        refreshed, len(settings.TRACKED_TICKERS),
        caps_updated, caps_no_data, caps_failed,
        sec["stored"], sec["failed"],
        extraction["catalysts"], extraction["processed"], extraction["prefiltered"],
        extraction["failed"], ", rate limited" if extraction["rate_limited"] else "",
        purged,
    )


async def get_fda_calendar(
    db: AsyncSession,
    days_ahead: int = 90,
) -> FDACalendarOut:
    """
    Return FDA decisions within the next `days_ahead` days;
    check the DB first, otherwise fetch from OpenFDA.
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

    # not enough pending rows in the DB — sync companies
    if len(pending) < 3:
        await sync_companies(db)
        for ticker in list(settings.TRACKED_TICKERS.keys())[:5]:
            await upsert_approvals(ticker, db)
        result = await db.execute(stmt)
        pending = result.scalars().all()

    # load company names
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
    """Fetch active trials from ClinicalTrials.gov by company name."""
    # v2: up to TRIALS_PAGE_SIZE trials and a full "phases" list per trial
    cache_key = "clinical_trials_v2"
    params = {"ticker": ticker}

    cached =await get_cached(db, cache_key, params)
    if cached is not None:
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
                "pageSize": TRIALS_PAGE_SIZE,
                "format": "json",
            },
        )
        studies = data.get("studies", [])
    except (httpx.HTTPError, ValueError):
        # failed requests aren't cached; the next call retries
        logger.exception("ClinicalTrials.gov request failed for %s", ticker)
        return []

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
                "phases": phase_list,  # e.g. ["PHASE1", "PHASE2"] for a combined trial
                "status": status_info.get("overallStatus", ""),
                "conditions": conditions.get("conditions", []),
            }
        )

    await set_cached(db, cache_key, params, trials)
    return trials
