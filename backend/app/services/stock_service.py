"""
yfinance integration — stock price history and company info.
if yfinance is unavailable, the last stored data is served from the DB
rate-limit errors are retried up to 3 attempts (waiting 2s, then 4s).
"""
import asyncio
import logging
from datetime import date, timedelta

import yfinance as yf
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yfinance.exceptions import YFRateLimitError

from app.models.models import Company, StockPrice
from app.schemas.schemas import StockPricePoint, StockHistoryOut
from app.services.cache_service import get_cached, set_cached

logger = logging.getLogger(__name__)

# timeout for a single yfinance call, in seconds
_YFINANCE_TIMEOUT = 12
_MAX_ATTEMPTS = 3

# versioned key: old entries use "date" instead of "price_date" and can't be parsed
_HISTORY_CACHE_KEY = "stock_history_v2"


async def _run_with_timeout(coro, timeout: float = _YFINANCE_TIMEOUT):
    """Try to cut an asyncio.to_thread call off after the given timeout."""
    return await asyncio.wait_for(coro, timeout=timeout)

async def get_stock_history(
    ticker: str,
    db: AsyncSession,
    period_days: int =365,
) -> StockHistoryOut:
    """
    Return the last 'period_days' days of price history for a ticker.
    cache first -> otherwise yfinance -> write to DB -> return
    """
    cache_key = _HISTORY_CACHE_KEY
    params ={"ticker": ticker, "days": period_days}

    cached = await get_cached(db, cache_key, params)
    if cached is not None:
        return StockHistoryOut(
            ticker=ticker,
            prices=[StockPricePoint(**p) for p in cached],
        )

    prices= await _fetch_from_yfinance(ticker, period_days)

    if not prices:
        # if yfinance fails, fall back to stored rows
        prices = await _load_from_db(ticker, db, period_days)

    if prices:
        await set_cached(db, cache_key , params, [p.model_dump() for p in prices])
        await _upsert_prices_to_db(ticker, prices, db)

    return StockHistoryOut(ticker=ticker, prices=prices)


async def _fetch_from_yfinance(ticker: str, period_days: int) -> list[StockPricePoint]:
    """Fetch from yfinance; on error / rate limit, log and return an empty list."""
    end = date.today()
    start = end - timedelta(days=period_days + 5)

    def _blocking_fetch() -> pd.DataFrame:
        tkr = yf.Ticker(ticker)
        return tkr.history(
            start=start.isoformat(), end=end.isoformat(), timeout=10
        )

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            df: pd.DataFrame = await _run_with_timeout(
                asyncio.to_thread(_blocking_fetch)
            )
        except YFRateLimitError:
            if attempt < _MAX_ATTEMPTS:
                wait = 2 ** attempt  # 2s, 4s
                logger.warning(
                    "yfinance rate limit for %s (attempt %d/%d), retrying in %ds",
                    ticker, attempt, _MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
                continue
            logger.error("yfinance rate limit for %s, giving up after %d attempts", ticker, attempt)
            return []
        except asyncio.TimeoutError:
            # timeout — don't retry
            logger.error("yfinance history timed out for %s after %ss", ticker, _YFINANCE_TIMEOUT)
            return []
        except Exception:
            logger.exception("yfinance history failed for %s", ticker)
            return []

        # rows with a NaN close can't be serialized to JSON
        df = df.dropna(subset=["Close"]) if "Close" in df.columns else df
        if df.empty:
            logger.warning("yfinance returned no price rows for %s", ticker)
            return []

        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]

        prices = []
        for _, row in df.iterrows():
            raw_date= row.get("date", row.get("datetime"))
            if hasattr(raw_date, "date"):
                price_date = raw_date.date()
            else:
                price_date = date.fromisoformat(str(raw_date)[:10])

            prices.append(
                StockPricePoint(
                    price_date=price_date,
                    open=_round_or_none(row.get("open")),
                    close=round(float(row["close"]), 4),
                    high=_round_or_none(row.get("high")),
                    low=_round_or_none(row.get("low")),
                    volume=None if pd.isna(row.get("volume")) else int(row["volume"]),
                )
            )
        return prices

    return []


def _round_or_none(v) -> float | None:
    return None if v is None or pd.isna(v) else round(float(v), 4)


async def _load_from_db(
    ticker: str, db: AsyncSession, period_days: int
) -> list[StockPricePoint]:
    """Load the last 'period_days' days of prices from the DB."""
    cutoff = date.today() - timedelta(days=period_days)
    stmt = (
        select(StockPrice)
        .where(StockPrice.ticker == ticker, StockPrice.price_date >= cutoff)
        .order_by(StockPrice.price_date)
    )
    result =await db.execute(stmt)
    rows =result.scalars().all()
    return [
        StockPricePoint(
            price_date=r.price_date,
            open=r.open,
            close=r.close,
            high=r.high,
            low=r.low,
            volume=r.volume,
        )
        for r in rows
    ]


async def _upsert_prices_to_db(
    ticker: str, prices: list[StockPricePoint], db: AsyncSession
) -> None:
    """Write prices to the StockPrice table (insert new dates only)."""
    stmt = select(StockPrice.price_date).where(StockPrice.ticker == ticker)
    result = await db.execute(stmt)
    existing_dates = {r for r in result.scalars().all()}

    for p in prices:
        if p.price_date not in existing_dates:
            db.add(
                StockPrice(
                    ticker=ticker,
                    price_date=p.price_date,
                    open=p.open,
                    close=p.close,
                    high=p.high,
                    low=p.low,
                    volume=p.volume,
                )
            )
    await db.commit()

async def get_company_info(ticker: str, db: AsyncSession) -> Company | None:
    """
    Return company info from the DB; otherwise fetch it from yfinance and store it.
    rate-limit errors are retried up to 3 attempts
    """
    company =await db.get(Company, ticker)
    if company and company.market_cap:
        return company

    def _blocking_fetch() -> dict:
        return yf.Ticker(ticker).get_info()

    info: dict | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            info = await _run_with_timeout(asyncio.to_thread(_blocking_fetch))
            break
        except YFRateLimitError:
            if attempt < _MAX_ATTEMPTS:
                wait = 2 ** attempt  # 2s, 4s
                logger.warning(
                    "yfinance rate limit on info for %s (attempt %d/%d), retrying in %ds",
                    ticker, attempt, _MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
                continue
            logger.error("yfinance rate limit on info for %s, giving up after %d attempts", ticker, attempt)
        except asyncio.TimeoutError:
            # timeout — fall back to what's in the DB
            logger.error("yfinance info timed out for %s after %ss", ticker, _YFINANCE_TIMEOUT)
            break
        except Exception:
            logger.exception("yfinance info failed for %s", ticker)
            break

    # for unknown tickers yfinance may return a near-empty dict — don't store a fake company
    if not info or not (info.get("longName") or info.get("shortName")):
        if info is not None:
            logger.warning("yfinance returned no company info for %s", ticker)
        return company

    name= info.get("longName") or info.get("shortName")
    sector = info.get("sector")
    market_cap = info.get("marketCap")
    description = info.get("longBusinessSummary")

    if company:
        company.name = name
        company.sector = sector
        company.market_cap = market_cap
        company.description = description
    else:
        company = Company(
            ticker=ticker,
            name=name,
            sector=sector,
            market_cap=market_cap,
            description=description,
        )
        db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


async def search_companies(query: str, db: AsyncSession) -> list[Company]:
    """Search the DB by ticker or company name."""
    q = f"%{query.lower()}%"
    stmt = select(Company).where(
        (Company.ticker.ilike(q)) | (Company.name.ilike(q))
    ).limit(20)
    result= await db.execute(stmt)
    return result.scalars().all()