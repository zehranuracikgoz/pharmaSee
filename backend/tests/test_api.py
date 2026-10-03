import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# db and external APIs are set up offline in conftest.py
from app.main import app
from app.database import init_db


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
    resp = await client.post("/fda/sync")
    assert resp.status_code==200
    assert resp.json()["status"] == "ok"


# stocks
@pytest.mark.asyncio
async def test_stock_info_known_ticker(client: AsyncClient):
    await client.post("/fda/sync")
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

    await client.post("/fda/sync")
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

    await client.post("/fda/sync")
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
    await client.post("/fda/sync")
    resp = await client.get("/stocks/MRNA/history?period_days=7")
    assert resp.status_code==200
    data = resp.json()
    assert "ticker" in data
    assert "prices" in data
    assert isinstance(data["prices"], list)

@pytest.mark.asyncio
async def test_search_companies(client: AsyncClient):
    await client.post("/fda/sync")
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
    await client.post("/fda/sync")
    resp = await client.get("/stocks/PFE/history?period_days=30")
    assert resp.status_code == 200
    prices = resp.json()["prices"]
    assert len(prices) >= 15
    assert {"price_date", "close"} <= prices[0].keys()


@pytest.mark.asyncio
async def test_fda_approvals_from_mocked_openfda(client: AsyncClient):
    await client.post("/fda/sync")
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

    await client.post("/fda/sync")
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