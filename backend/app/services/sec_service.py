"""
SEC EDGAR filings for tracked companies: 8-K press releases / other events and 6-Ks
(foreign issuers such as BNTX and ARGX). stored as plain text for a later llm step
that extracts upcoming catalysts (PDUFA dates, AdComs, trial readouts).
"""
import asyncio
import logging
import re
import time
from datetime import date, timedelta

import httpx
from bs4 import BeautifulSoup, Comment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.models import SecFiling
from app.services.cache_service import get_cached, set_cached

logger = logging.getLogger(__name__)

TICKERS_URL ="https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"

LOOKBACK_DAYS = 180
MAX_TEXT_CHARS = 30_000
KEEP_8K_ITEMS = {"7.01", "8.01"}  # reg FD press releases, other events
CIK_MAP_TTL = 7 * 24 * 3600

# sec allows 10 requests/second; stay well under it
_MIN_REQUEST_INTERVAL = 0.15

# exhibit 99.1 file names vary by filer agent: ex99-1.htm, d18337dex991.htm, exhibit991.htm,
# and workiva-style a991bntx_q22026pressreleas.htm (index.json has no document types)
_EX991_NAME = re.compile(r"ex(hibit)?[-_.]?99[-_.]?0?1(?!\d)|^a99[-_.]?1(?!\d)", re.I)
_TEXT_DOC = re.compile(r"\.(html?|txt)$", re.I)

# edgar wraps documents in sgml-style headers: <TYPE>EX-99.1 <SEQUENCE>2 <FILENAME>...
_EDGAR_HEADER_TAGS =re.compile(r"<(TYPE|SEQUENCE|FILENAME|DESCRIPTION)>[^<\r\n]*", re.I)
_BLOCK_TAGS = ["p", "div", "br", "tr", "li", "ul", "ol", "table", "section", "blockquote",
               "h1", "h2", "h3", "h4", "h5", "h6"]


class _SecClient:
    """httpx client with the sec user-agent and a simple request throttle"""

    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def get(self, url: str) ->httpx.Response:
        async with self._lock:
            wait = self._last + _MIN_REQUEST_INTERVAL - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp


def html_to_text(html: str) -> str:
    """plain text from a filing document, without scripts, styles or hidden xbrl data"""
    soup = BeautifulSoup(_EDGAR_HEADER_TAGS.sub("", html), "html.parser")
    for tag in soup(["script", "style", "head", "title", "ix:header"]):
        tag.decompose()
    for tag in soup.select('[style*="display:none"], [style*="display: none"]'):
        tag.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

   #source line breaks are just formatting: collapse them, then break only between blocks
    for s in soup.find_all(string=True):
        s.replace_with(re.sub(r"\s+", " ", s))
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    for cell in soup.find_all(["td", "th"]):
        cell.insert_after(" ")

    lines = [re.sub(r" {2,}", " ", line).strip() for line in soup.get_text().split("\n")]
    text =re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text[:MAX_TEXT_CHARS]


def _wanted(form: str, items: str) -> bool:
    if form == "6-K":
        return True
    if form == "8-K":
        return bool(KEEP_8K_ITEMS & {i.strip() for i in items.split(",")})
    return False


async def _cik_map(sec: _SecClient, db: AsyncSession) -> dict[str, int]:
    cached =await get_cached(db, "sec_cik_map", {})
    if cached is not None:
        return cached
    data = (await sec.get(TICKERS_URL)).json()
    cik_map = {row["ticker"].upper(): int(row["cik_str"]) for row in data.values()}
    await set_cached(db, "sec_cik_map", {}, cik_map, ttl_seconds=CIK_MAP_TTL)
    return cik_map


def _recent_filings(submissions: dict, since: date) -> list[dict]:
    """8-K (items 7.01/8.01) and 6-K filings filed on or after `since`"""
    recent = submissions.get("filings", {}).get("recent", {})
    all_items = recent.get("items") or []
    out = []
    for i, form in enumerate(recent.get("form", [])):
        items = (all_items[i] if i< len(all_items) else "") or ""
        filed = date.fromisoformat(recent["filingDate"][i])
        if filed >= since and _wanted(form, items):
            out.append({
                "accession_number": recent["accessionNumber"][i],
                "form": form,
                "items": items or None,
                "filed_date": filed,
                "primary_document": recent["primaryDocument"][i],
            })
    return out


async def _filing_document(sec: _SecClient, cik: int, filing: dict) -> tuple[str, str]:
    """(url, text) of the EX-99.1 exhibit if there is one, otherwise the primary document"""
    base =ARCHIVE_URL.format(cik=cik, acc=filing["accession_number"].replace("-", ""))
    index = (await sec.get(f"{base}/index.json")).json()
    names = [item["name"] for item in index.get("directory", {}).get("item", [])]
    exhibit = next((n for n in names if _EX991_NAME.search(n) and _TEXT_DOC.search(n)), None)
    doc = exhibit or filing["primary_document"]

    url = f"{base}/{doc}"
    resp = await sec.get(url)
    text = html_to_text(resp.text) if re.search(r"\.html?$", doc, re.I) else resp.text[:MAX_TEXT_CHARS]
    return url, text


async def _sync_ticker(sec: _SecClient, db: AsyncSession, ticker: str, cik: int) -> tuple[int, int]:
    """store new filings for one ticker; returns (stored, already_stored)"""
    submissions = (await sec.get(SUBMISSIONS_URL.format(cik=cik))).json()
    filings = _recent_filings(submissions, date.today() - timedelta(days=LOOKBACK_DAYS))
    if not filings:
        return 0, 0

    accessions = [f["accession_number"] for f in filings]
    known = set(
        await db.scalars(
            select(SecFiling.accession_number).where(SecFiling.accession_number.in_( accessions))
        )
    )
    stored = 0
    for filing in filings:
        if filing["accession_number"] in known:
            continue  #never re-download a stored filing
        url, text = await _filing_document(sec, cik, filing)
        db.add(SecFiling(
            accession_number=filing["accession_number"],
            ticker=ticker,
            form=filing["form"],
            items=filing["items"],
            filed_date=filing["filed_date"],
            url=url,
            text=text,
        ))
        await db.commit()  # keep progress if a later filing fails
        stored += 1
    return stored, len(known)


async def sync_sec_filings(db: AsyncSession | None = None) -> dict:
    """fetch and store recent 8-K / 6-K filings for every tracked ticker"""
    if db is None:
        async with AsyncSessionLocal() as session:
            return await sync_sec_filings(session)

    summary ={"stored": 0, "already_stored": 0, "failed": 0, "error": None}
    if not settings.SEC_CONTACT_EMAIL:
        summary["error"] = "SEC_CONTACT_EMAIL is not set"
        logger.error("sec sync skipped: SEC_CONTACT_EMAIL is not set")
        return summary

    headers = {
        "User-Agent": f"PharmaSee {settings.SEC_CONTACT_EMAIL}",
        "Accept-Encoding": "gzip, deflate",
    }
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        sec = _SecClient(client)
        try:
            cik_map =await _cik_map(sec, db)
        except (httpx.HTTPError, ValueError):
            logger.exception("sec sync failed: could not load the ticker -> CIK map")
            summary["error"] = "could not load the SEC ticker map"
            return summary

        for ticker in settings.TRACKED_TICKERS:
            cik = cik_map.get(ticker)
            if cik is None:
                logger.warning("no SEC CIK for %s", ticker)
                summary["failed"] += 1
                continue
            try:
                stored, already = await _sync_ticker(sec, db, ticker, cik)
                summary["stored"] += stored
                summary["already_stored"] += already
            except Exception:
                summary["failed"] += 1
                logger.exception("sec sync failed for %s", ticker)
                await db.rollback()  # keep the session usable for the next ticker

    logger.info(
        "sec sync done: %d new filings stored, %d already stored, %d/%d tickers failed",
        summary["stored"], summary["already_stored"], summary["failed"], len(settings.TRACKED_TICKERS),
    )
    
    return summary