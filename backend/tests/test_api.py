import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# db and external APIs are set up offline in conftest.py
from app.main import app
from app.database import init_db
from tests.conftest import TEST_ADMIN_TOKEN

ADMIN = {"X-Admin-Token": TEST_ADMIN_TOKEN}


@pytest_asyncio.fixture(scope="module")
async def client():
    await init_db()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url = "http://test"
    ) as ac:
        yield ac


# health checks
@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["name"] == "PharmaSee API"


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


# FDA
@pytest.mark.asyncio
async def test_fda_sync(client: AsyncClient):
    # also the "right admin token" case
    resp = await client.post("/fda/sync", headers=ADMIN)
    assert resp.status_code==200
    assert resp.json()["status"] == "ok"


ADMIN_ENDPOINTS = ["/fda/sync", "/sec/sync", "/sec/extract", "/sec/reextract"]


@pytest.mark.asyncio
async def test_admin_endpoints_reject_missing_token(client: AsyncClient):
    for url in ADMIN_ENDPOINTS:
        assert (await client.post(url)).status_code == 401, url


@pytest.mark.asyncio
async def test_admin_endpoints_reject_wrong_token(client: AsyncClient):
    for url in ADMIN_ENDPOINTS:
        resp = await client.post(url, headers={"X-Admin-Token": "wrong-token"})
        assert resp.status_code == 401, url


# stocks
@pytest.mark.asyncio
async def test_stock_info_known_ticker(client: AsyncClient):
    await client.post("/fda/sync", headers=ADMIN)
    resp = await client.get("/stocks/MRNA/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "MRNA"


@pytest.mark.asyncio
async def test_stock_info_unknown_ticker(client: AsyncClient):
    resp = await client.get("/stocks/XXXXUNKNOWN/info")
    assert resp.status_code == 404


async def _reset_company(ticker: str):
    from app.database import AsyncSessionLocal
    from app.models.models import Company

    async with AsyncSessionLocal() as db:
        company = await db.get(Company, ticker)
        company.market_cap = None
        company.sector = None
        await db.commit()


def _blocked_info_ticker(fast_market_cap):
    """yfinance.Ticker whose .info is blocked (near-empty dict, as from cloud ips)"""
    from types import SimpleNamespace

    from tests.conftest import FakeTicker

    class BlockedInfoTicker(FakeTicker):
        def __init__(self, ticker, *args, **kwargs):
            super().__init__(ticker, *args, **kwargs)
            self.info = {"trailingPegRatio": None}
            self.fast_info =  SimpleNamespace(market_cap=fast_market_cap)

    return BlockedInfoTicker


@pytest.mark.asyncio
async def test_stock_info_falls_back_to_fast_info(client: AsyncClient, monkeypatch):
    import yfinance

    from tests.conftest import FAST_INFO_MARKET_CAP

    await client.post("/fda/sync", headers=ADMIN)
    await _reset_company("VRTX")
    monkeypatch.setattr(yfinance, "Ticker", _blocked_info_ticker(FAST_INFO_MARKET_CAP))

    resp = await client.get("/stocks/VRTX/info")
    assert resp.status_code== 200
    data = resp.json()
    assert data["market_cap"] == FAST_INFO_MARKET_CAP
    assert data["sector"] is None  # never filled with a guess


@pytest.mark.asyncio
async def test_failed_stock_info_is_not_stored(client: AsyncClient, monkeypatch):
    import yfinance

    from tests.conftest import FakeTicker

    await client.post("/fda/sync", headers=ADMIN)
    await _reset_company("GILD")

    #.info blocked and fast_info empty: nothing usable, nothing stored
    monkeypatch.setattr(yfinance, "Ticker", _blocked_info_ticker(None))
    resp = await client.get("/stocks/GILD/info")
    assert resp.status_code == 200
    assert resp.json()["market_cap"] is None

    # the next request tries yfinance again and gets the real data
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)
    data  = (await client.get("/stocks/GILD/info")).json()
    assert data["market_cap"] == 50_000_000_000
    assert data["sector"] == "Healthcare"


@pytest.mark.asyncio
async def test_stock_history_returns_valid_structure(client: AsyncClient):
    # prices can be empty in sandbox, just check the shape
    await client.post("/fda/sync", headers=ADMIN)
    resp = await client.get("/stocks/MRNA/history?period_days=7")
    assert resp.status_code==200
    data = resp.json()
    assert "ticker" in data
    assert "prices" in data
    assert isinstance(data["prices"], list)

@pytest.mark.asyncio
async def test_search_companies(client: AsyncClient):
    await client.post("/fda/sync", headers=ADMIN)
    resp = await client.get("/stocks/search?q=moderna")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["query"] == "moderna"


# analysis
@pytest.mark.asyncio
async def test_momentum_endpoint_structure(client: AsyncClient):
    # momentum_pct can be null — shouldn't raise
    resp = await client.get(
        "/analysis/momentum?ticker=MRNA&event_date=2023-08-28"
    )
    assert resp.status_code == 200
    data=resp.json()
    assert data["ticker"] == "MRNA"
    assert "event_date" in data
    assert "momentum_pct" in data


@pytest.mark.asyncio
async def test_compare_endpoint_structure(client: AsyncClient):
    resp = await client.get("/analysis/compare?a=MRNA&b=BNTX")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker_a"] == "MRNA"
    assert data["ticker_b"] == "BNTX"
    assert "history_a" in data
    assert "history_b" in data


# companies
@pytest.mark.asyncio
async def test_tracked_companies(client: AsyncClient):
    resp = await client.get("/companies")
    assert resp.status_code == 200
    tickers = [c["ticker"] for c in resp.json()]
    assert "ALNY" in tickers and "ARGX" in tickers
    assert "SGEN" not in tickers and "BLUE" not in tickers


# fda parsing / dedupe
_FAKE_OPENFDA = [
    {
        "application_number": "BLA761339",
        "openfda": {"brand_name": ["BRANDX"], "generic_name": ["genericx"]},
        "submissions": [
            {"submission_type": "ORIG", "submission_number": "1", "submission_status": "AP",
             "submission_status_date": "20230115", "submission_class_code": "TYPE 1"},
            {"submission_type": "SUPPL", "submission_number": "4", "submission_status": "AP",
             "submission_status_date": "20240301", "submission_class_code": "EFFICACY"},
            {"submission_type": "SUPPL", "submission_number": "5", "submission_status": "AP",
             "submission_status_date": "20240601", "submission_class_code": "LABELING"},
            {"submission_type": "SUPPL", "submission_number": "6", "submission_status": "AP",
             "submission_status_date": "20240701", "submission_class_code": "MANUF (CMC)"},
        ],
    }
]


def test_parse_approvals_filters_noise_and_uses_stable_ids():
    from app.services.fda_service import parse_approvals

    rows = parse_approvals("TEST", _FAKE_OPENFDA)
    assert sorted(r["id"] for r in rows) == ["TEST-BLA761339-ORIG-1", "TEST-BLA761339-SUPPL-4"]
    assert all(r["application_type"] == "BLA" for r in rows)
    # same input -> same ids
    assert parse_approvals("TEST", _FAKE_OPENFDA) == rows


@pytest.mark.asyncio
async def test_upsert_approvals_is_idempotent(client: AsyncClient):
    from sqlalchemy import func, select

    from app.database import AsyncSessionLocal
    from app.models.models import Company, DrugApproval
    from app.services.cache_service import set_cached
    from app.services.fda_service import (
        _APPROVALS_CACHE_KEY,
        parse_approvals,
        upsert_approvals,
    )

    async with AsyncSessionLocal() as db:
        if not await db.get(Company, "TESTX"):
            db.add(Company(ticker="TESTX", name="Testx"))
            await db.commit()
        # seed the cache so no OpenFDA call is made
        await set_cached(
            db, _APPROVALS_CACHE_KEY, {"ticker": "TESTX"}, parse_approvals("TESTX", _FAKE_OPENFDA)
        )

        await upsert_approvals("TESTX", db)
        await upsert_approvals("TESTX", db)

        count = await db.scalar(
            select(func.count()).select_from(DrugApproval).where(DrugApproval.company_id == "TESTX")
        )
        assert count == 2


@pytest.mark.asyncio
async def test_co_marketed_application_kept_for_each_company(client: AsyncClient):
    # same drug application for two companies (pfizer/biontech) -> one row each
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.models import Company, DrugApproval
    from app.services.cache_service import set_cached
    from app.services.fda_service import (
        _APPROVALS_CACHE_KEY,
        parse_approvals,
        upsert_approvals,
    )

    async with AsyncSessionLocal() as db:
        for ticker in ("COMA", "COMB"):
            if not await db.get(Company, ticker):
                db.add(Company(ticker=ticker, name=ticker))
            await db.commit ()
            await set_cached(
                db, _APPROVALS_CACHE_KEY, {"ticker": ticker}, parse_approvals(ticker, _FAKE_OPENFDA)
            )
            
            await upsert_approvals(ticker, db)

        rows = (
            await db.execute(
                select(DrugApproval.company_id).where(DrugApproval.company_id.in_(["COMA", "COMB"]))
            )
        ).scalars().all()
        assert sorted(rows) == ["COMA", "COMA", "COMB", "COMB"]


# mocked data flows through the app (not just the response shape)
@pytest.mark.asyncio
async def test_stock_history_returns_mocked_prices(client: AsyncClient):
    await client.post("/fda/sync", headers=ADMIN)
    resp = await client.get("/stocks/PFE/history?period_days=30")
    assert resp.status_code == 200
    prices = resp.json()["prices"]
    assert len(prices) >= 15
    assert {"price_date", "close"} <= prices[0].keys()


@pytest.mark.asyncio
async def test_fda_approvals_from_mocked_openfda(client: AsyncClient):
    await client.post("/fda/sync", headers=ADMIN)
    resp = await client.get("/fda/REGN/approvals")
    assert resp.status_code == 200
    approvals = resp.json()
    # orig + efficacy supplement kept, labeling supplement filtered out
    assert all(a["id"].startswith("REGN-") for a in approvals)
    assert sorted("-".join(a["id"].split("-")[-2:]) for a in approvals) == ["ORIG-1", "SUPPL-4"]
    assert {a["drug_name"] for a in approvals} =={"testumab"}


@pytest.mark.asyncio
async def test_scheduled_sync_refreshes_all_tickers(client: AsyncClient):
    from sqlalchemy import func, select

    from app.config import settings
    from app.database import AsyncSessionLocal
    from app.models.models import DrugApproval
    from app.services.fda_service import run_scheduled_sync

    await run_scheduled_sync()

    async with AsyncSessionLocal() as db:
        tickers = await db.scalars(select(DrugApproval.company_id).distinct())
        assert set(tickers) >= set(settings.TRACKED_TICKERS)
        count = await db.scalar(
            select(func.count()).select_from(DrugApproval).where(DrugApproval.company_id == "PFE")
        )
        assert count==2


@pytest.mark.asyncio
async def test_market_cap_refresh_isolates_failures(client: AsyncClient, monkeypatch):
    import yfinance
    from sqlalchemy import select

    from app.config import settings
    from app.database import AsyncSessionLocal
    from app.models.models import Company
    from app.services.stock_service import refresh_market_caps
    from tests.conftest import FakeTicker

    class BrokenFastInfo:
        @property
        def market_cap(self):
            raise RuntimeError("yahoo down")

    class PfeFailsTicker(FakeTicker):
        # yfinance fails completely for PFE (.info and fast_info), works for the rest
        def __init__(self, ticker, *args, **kwargs):
            super().__init__(ticker, *args, **kwargs)
            if self.ticker == "PFE":
                self.fast_info = BrokenFastInfo()

        def get_info(self):
            if self.ticker == "PFE":
                raise RuntimeError("yahoo down")
            return super().get_info()

    await client.post("/fda/sync", headers=ADMIN)
    async with AsyncSessionLocal() as db:
        for company in await db.scalars(select(Company)):
            company.market_cap = 1.0  # stale value
        await db.commit()

    monkeypatch.setattr(yfinance, "Ticker", PfeFailsTicker)
    async with AsyncSessionLocal() as db:
        updated, no_data, failed = await refresh_market_caps(db)

    assert (updated, no_data, failed) == (len(settings.TRACKED_TICKERS) - 1, 1, 0)
    async with AsyncSessionLocal() as db:
        caps = {c.ticker: c.market_cap for c in await db.scalars(select(Company))}
    assert caps["PFE"] == 1.0  # nothing came back: stored value kept
    assert all(caps[t] == 50_000_000_000 for t in settings.TRACKED_TICKERS if t != "PFE")


# sec filings
@pytest.mark.asyncio
async def test_sec_sync_filters_prefers_ex991_and_skips_stored(client: AsyncClient):
    from sqlalchemy import delete, select

    from app.database import AsyncSessionLocal
    from app.models.models import Catalyst, SecFiling
    from tests.conftest import SEC_REQUESTS

    async with AsyncSessionLocal() as db:  # the scheduled sync test may have stored some
        await db.execute(delete(Catalyst))
        await db.execute(delete(SecFiling))
        await db.commit()

    resp = await client.post("/sec/sync", headers=ADMIN)
    assert resp.status_code == 200
    assert resp.json()["stored"] == 2

    async with AsyncSessionLocal() as db:
        rows = {r.ticker: r for r in await db.scalars(select(SecFiling))}
    # filters:only the 7.01 8-K and the 6-K (2.02 8-K, 10-Q and old 8-K dropped)
    assert {t: r.form for t, r in rows.items()} == {"MRNA": "8-K", "BNTX": "6-K"}
    # EX-99.1 preferred over the 8-K cover document; hidden xbrl and styles stripped
    mrna = rows["MRNA"]
    assert mrna.url.endswith("/ex99-1.htm") and mrna.items == "7.01,9.01"
    assert mrna.text == "Moderna announces FDA PDUFA date of December 1."
    # no exhibit: the 6-K's primary document is used
    assert rows["BNTX"].url.endswith("/form6-k.htm") and rows["BNTX"].processed is False

    # re-run: nothing new stored, no filing index or document downloaded again
    seen = len(SEC_REQUESTS)
    resp=await client.post("/sec/sync", headers=ADMIN)
    assert resp.json()["stored"] == 0 and resp.json()["already_stored"] == 2
    assert not [u for u in SEC_REQUESTS[seen:] if "/Archives/" in u]
    async with AsyncSessionLocal() as db:
        assert len((await db.scalars(select(SecFiling))).all()) == 2


# catalyst extraction
async def _reset_filings(*filings: tuple):
    """replace stored filings with (accession, text[, filed_date]) rows for MRNA"""
    from datetime import date

    from sqlalchemy import delete

    from app.database import AsyncSessionLocal
    from app.models.models import Catalyst, SecFiling

    async with AsyncSessionLocal() as db:
        await  db.execute(delete(Catalyst))
        await db.execute(delete(SecFiling))
        for accession, text, *filed in filings:
            db.add(SecFiling(accession_number=accession, ticker="MRNA", form="8-K", items="8.01",
                             filed_date=filed[0] if filed else date(2026, 9, 1),
                             url= f"https://sec.test/{accession}", text=text))
        await db.commit()


async def _filing_states() -> dict[str, bool]:
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.models import SecFiling

    async with AsyncSessionLocal() as db:
        return {f.accession_number: f.processed for f in await db.scalars(select(SecFiling))}


@pytest.mark.asyncio
async def test_prefilter_skips_filing_without_calling_llm(client: AsyncClient):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_CALLS

    await _reset_filings(("acc-plain", "The board declared a quarterly dividend."))
    summary= await process_pending_filings()

    assert summary["prefiltered"] == 1 and summary["llm_calls"] == 0
    assert GEMINI_CALLS == []
    assert await _filing_states() == {"acc-plain": True}


@pytest.mark.asyncio
async def test_catalyst_with_quote_not_in_filing_is_dropped(client: AsyncClient):
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.models import Catalyst
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE

    text = "Moderna said the FDA set a PDUFA date of March 15, 2027 for mRNA-1010.\nOther news."
    await _reset_filings(("acc-pdufa", text))
    base = {"indication": "flu", "date_precision": "day", "summary": "PDUFA date set."}
    GEMINI_QUEUE.append([
        #a line break inside the quote still matches the stored text after normalization
        {**base, "event_type": "pdufa", "drug": "mRNA-1010", "date_text": "March 15, 2027",
         "event_date": "2027-03-15",
         "source_quote": "Moderna said the FDA set a PDUFA date of March 15,\n2027 for mRNA-1010."},
        {**base, "event_type": "approval", "drug": "mRNA-9999", "date_text": None, "event_date": None,
         "source_quote": "The FDA approved mRNA-9999 yesterday."},  # not in the filing
    ])

    summary = await process_pending_filings()
    assert summary["catalysts"] == 1 and summary["quotes_dropped"] == 1
    async with AsyncSessionLocal() as db:
        rows =(await db.scalars(select(Catalyst))).all()
    assert [(r.drug, r.event_type, str(r.event_date)) for r in rows] == [("mRNA-1010", "pdufa", "2027-03-15")]
    assert await _filing_states() == {"acc-pdufa": True}


@pytest.mark.asyncio
async def test_rate_limit_leaves_remaining_filings_unprocessed(client: AsyncClient):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_CALLS, GEMINI_QUEUE

    await _reset_filings(
        ("acc-1", "Topline Phase 3 data expected in Q1 2027."),
        ("acc-2", "The FDA accepted the BLA for priority review."),
        ("acc-3", "Pivotal trial enrollment completed ahead of a data readout."),
    )
    GEMINI_QUEUE.append(429)

    summary =  await process_pending_filings()
    assert summary["rate_limited"] and summary["processed"] == 0
    assert len(GEMINI_CALLS) == 1  # stopped after the first 429
    assert await _filing_states() == {"acc-1": False, "acc-2": False, "acc-3": False}


def test_default_gemini_model_is_flash_lite():
    from app.config import Settings

    assert Settings.model_fields["GEMINI_MODEL"].default == "gemini-3.5-flash-lite"


async def  _stored_catalysts():
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.models import Catalyst

    async with AsyncSessionLocal() as db:
        return (await db.scalars(select(Catalyst))).all()


@pytest.mark.asyncio
async def test_undated_approval_gets_filing_date(client: AsyncClient):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE

    await _reset_filings(("acc-approved", "The FDA approved Fluvax for seasonal influenza."))
    GEMINI_QUEUE.append([{
        "event_type": "approval", "drug": "Fluvax", "indication": "influenza", "date_text": None,
        "event_date": None, "date_precision": "none", "summary": "FDA approved Fluvax.",
        "source_quote": "The FDA approved Fluvax for seasonal influenza.",
    }])

    await process_pending_filings()
    [row]= await _stored_catalysts()
    assert (str(row.event_date), row.date_precision, row.date_text) == (
        "2026-09-01", "day", "Announced September 1, 2026"
    )


@pytest.mark.asyncio
async def test_forward_looking_approval_is_reclassified(client: AsyncClient):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE

    quote = "Intellia is advancing lonvoguran ziclumeran toward a planned U.S. approval."
    await _reset_filings(("acc-planned", quote))
    GEMINI_QUEUE.append([{
        "event_type": "approval", "drug": "lonvoguran ziclumeran", "indication": "HAE", "date_text": None,
        "event_date": None, "date_precision": "none", "summary": "Planned U.S. approval.",
        "source_quote": quote,
    }])

    await process_pending_filings()
    [row] = await _stored_catalysts()
    # no filing date fallback: it is not an announced decision
    assert (row.event_type, row.event_date, row.date_text) == ("other", None, None)


@pytest.mark.asyncio
async def test_pdufa_target_date_is_stored(client: AsyncClient):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE

    quote = ("The FDA accepted the BLA for NTLA-2001 with Priority Review and assigned "
             "a PDUFA target action date of March 15, 2027.")
    await _reset_filings(("acc-bla", quote))
    base = {"drug": "NTLA-2001", "indication": "ATTR-CM", "source_quote": quote}
    GEMINI_QUEUE.append([
        {**base, "event_type": "regulatory_submission", "date_text": None, "event_date": None,
         "date_precision": "none", "summary": "FDA accepted the BLA."},
        {**base, "event_type": "pdufa", "date_text": "March 15, 2027", "event_date": "2027-03-15",
         "date_precision": "day", "summary": "PDUFA target action date."},
    ])

    await process_pending_filings()
    rows = {r.event_type: r for r in await _stored_catalysts()}
    assert set(rows) == {"regulatory_submission", "pdufa"}
    assert (str(rows["pdufa"].event_date), rows["pdufa"].date_precision) == ("2027-03-15", "day")


@pytest.mark.asyncio
async def test_relative_date_text_uses_filing_date(client: AsyncClient):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE

    quote = "Moderna today reported positive topline Phase 3 results for mRNA-1010."
    await _reset_filings(("acc-today", quote))
    GEMINI_QUEUE.append([{
        "event_type": "topline_readout", "drug": "mRNA-1010", "indication": "flu", "date_text": "Today",
        "event_date": "2026-08-30", "date_precision": "day", "summary": "Positive topline results.",
        "source_quote": quote,
    }])

    await process_pending_filings()
    [row] = await _stored_catalysts()
    assert (str(row.event_date), row.date_precision, row.date_text) == (
        "2026-09-01", "day", "Announced September 1, 2026"
    )


@pytest.mark.asyncio
async def test_dedupe_uses_normalized_drug_name(client: AsyncClient):
    from datetime import date

    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE

    new_text = "Phase 3 data for Trastuzumab Pamirtecan expected in Q4 2026."
    old_text ="Update: Phase 3 data for trastuzumab pamirtecan (BNT323/DB-1303) are expected in Q4 2026."
    # shortest first: the newer filing is processed before the older one
    await _reset_filings(("acc-new", new_text, date(2026, 9, 20)), ("acc-old", old_text, date(2026, 8, 1)))
    base = {"event_type": "topline_readout", "indication": "breast cancer", "date_text": "Q4 2026",
            "event_date": "2026-10-01", "date_precision": "quarter", "summary": "Phase 3 data in Q4."}
    GEMINI_QUEUE.extend([
        [{**base, "drug": "Trastuzumab Pamirtecan", "source_quote": new_text}],
        [{**base, "drug": "trastuzumab  pamirtecan (BNT323/DB-1303)", "source_quote": old_text}],
    ])

    await process_pending_filings()
    rows = await _stored_catalysts ()
    # one row, from the newer filing, with its name as written
    assert [(r.accession_number, r.drug) for r in rows] == [("acc-new", "Trastuzumab Pamirtecan")]


# cross-model voting
VOTE_TEXT = "The FDA set a PDUFA date of March 15, 2027 for mRNA-1010. Phase 3 data for mRNA-1083 are expected in Q1 2027."
PDUFA_1010 = {"event_type": "pdufa", "drug": "mRNA-1010", "indication": "flu", "date_text": "March 15, 2027",
              "event_date": "2027-03-15", "date_precision": "day", "summary": "PDUFA date set.",
              "source_quote": "The FDA set a PDUFA date of March 15, 2027 for mRNA-1010."}


@pytest.fixture
def two_models(monkeypatch):
    from types import SimpleNamespace

    from app.services import llm_service
    from tests.conftest import SECOND_LLM_HOST

    # duck-typed provider: only gemini is registered in the app
    second = SimpleNamespace(name="second", kind="openai", key_setting="SECOND_API_KEY", api_key="test-key",
                             model="test-model", min_interval=0, base_url=f"https://{SECOND_LLM_HOST}/v1")
    monkeypatch.setattr(llm_service, "PROVIDERS", [*llm_service.PROVIDERS, second])


def _votes(rows):
    return sorted((r.drug, r.votes, r.models_total, r.agreed_by) for r in rows)


@pytest.mark.asyncio
async def test_models_agree_one_row_two_votes(client: AsyncClient, two_models):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE, SECOND_QUEUE

    await _reset_filings(("acc-vote", VOTE_TEXT))
    GEMINI_QUEUE.append([PDUFA_1010])
    # the second model names it differently: one name contains the other, still the same event
    SECOND_QUEUE.append([{**PDUFA_1010, "drug": "mRNA-1010 influenza vaccine", "summary": "Second model wording."}])

    summary = await process_pending_filings()
    rows = await _stored_catalysts()
    assert _votes(rows) == [("mRNA-1010", 2, 2, "gemini,second")]
    assert rows[0].summary == "PDUFA date set."  # gemini's text is kept
    assert summary["calls"] == {"gemini": 1, "second": 1} and summary["full_agreement"] == 1


@pytest.mark.asyncio
async def test_models_disagree_two_rows_one_vote_each(client: AsyncClient, two_models):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE, SECOND_QUEUE

    await _reset_filings(("acc-vote", VOTE_TEXT))
    GEMINI_QUEUE.append([PDUFA_1010])
    SECOND_QUEUE.append([{
        "event_type": "topline_readout", "drug": "mRNA-1083", "indication": "flu/covid", "date_text": "Q1 2027",
        "event_date": "2027-01-01", "date_precision": "quarter", "summary": "Phase 3 data in Q1 2027.",
        "source_quote": "Phase 3 data for mRNA-1083 are expected in Q1 2027.",
    }])

    summary = await process_pending_filings()
    assert _votes(await _stored_catalysts()) == [("mRNA-1010", 1, 2, "gemini"), ("mRNA-1083", 1, 2, "second")]
    assert summary["partial_agreement"] == 2


@pytest.mark.asyncio
async def test_gemini_only_works_as_before(client: AsyncClient):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE, SECOND_CALLS

    await _reset_filings(("acc-vote", VOTE_TEXT))
    GEMINI_QUEUE.append([PDUFA_1010])

    summary = await process_pending_filings()
    assert _votes(await _stored_catalysts()) == [("mRNA-1010", 1, 1, "gemini")]
    assert SECOND_CALLS == [] and summary["calls"] == {"gemini": 1}


@pytest.mark.asyncio
async def test_invalid_json_from_one_model_still_saves_filing(client: AsyncClient, two_models):
    from app.services.catalyst_service import process_pending_filings
    from tests.conftest import GEMINI_QUEUE, SECOND_QUEUE

    await _reset_filings(("acc-vote", VOTE_TEXT))
    GEMINI_QUEUE.append([PDUFA_1010])
    SECOND_QUEUE.append('{"catalysts": [{"event_type": "pdufa"')  # cut off mid-reply

    summary = await process_pending_filings()
    assert _votes(await _stored_catalysts()) == [("mRNA-1010", 1, 1, "gemini")]
    assert summary["provider_errors"] == {"gemini": 0, "second": 1}
    assert await _filing_states() == {"acc-vote": True}


# cache
@pytest.mark.asyncio
async def test_cache_hit_faster_than_miss(client: AsyncClient):
    import time

    t0 = time.perf_counter()
    await client.get("/stocks/MRNA/history?period_days=7")
    t_miss = time.perf_counter() - t0

    t0 = time.perf_counter()
    await client.get("/stocks/MRNA/history?period_days=7")
    t_hit = time.perf_counter() - t0

    # loose check — cache hit should be noticeably faster
    assert t_hit < t_miss + 0.5