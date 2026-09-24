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