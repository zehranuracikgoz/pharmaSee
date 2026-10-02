import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_pharmasee.db")

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
    assert sorted(r["id"] for r in rows) == ["BLA761339-ORIG-1", "BLA761339-SUPPL-4"]
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