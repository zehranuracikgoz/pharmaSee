"""
yfinance entegrasyonu — hisse fiyatı geçmişi ve şirket bilgisi.
yfinance erişim kesintisinde önbellekteki son geçerli veri döndürülür
429 rate-limit hatalarında 3 kez yeniden dener (2s, 4s, 8s bekleyip).
"""
import asyncio
from datetime import date, timedelta

import yfinance as yf
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Company, StockPrice
from app.schemas.schemas import StockPricePoint, StockHistoryOut
from app.services.cache_service import get_cached, set_cached

# yfinance için tekil çağrı zaman aşımı-saniye
_YFINANCE_TIMEOUT = 12


async def _run_with_timeout(coro, timeout: float = _YFINANCE_TIMEOUT):
    """asyncio.to_thread çağrısını belirtilen sürede kesmeye çalışır"""
    return await asyncio.wait_for(coro, timeout=timeout)

async def get_stock_history(
    ticker: str,
    db: AsyncSession,
    period_days: int =365,
) -> StockHistoryOut:
    """
    ticker için son 'period_days' günlük hisse geçmişini döndür
    önce önbellek -> yoksa yfinance -> DB'ye yaz -> döndür
    """
    cache_key = "stock_history"
    params ={"ticker": ticker, "days": period_days}

    cached = await get_cached(db, cache_key, params)
    if cached:
        return StockHistoryOut(
            ticker=ticker,
            prices=[StockPricePoint(**p) for p in cached],
        )

    prices= await _fetch_from_yfinance(ticker, period_days)

    if not prices:
        # yfinance başarısızsa DB den son kayıtları dene
        prices = await _load_from_db(ticker, db, period_days)

    if prices:
        await set_cached(db, cache_key , params, [p.model_dump() for p in prices])
        await _upsert_prices_to_db(ticker, prices, db)

    return StockHistoryOut(ticker=ticker, prices=prices)


async def _fetch_from_yfinance(ticker: str, period_days: int) -> list[StockPricePoint]:
    """yfinance dan veri çek: hata / rate-limit durumunda boş liste döndür"""
    for attempt in range(3):
        try:
            end = date.today()
            start = end-timedelta(days=period_days + 5)

            def _blocking_fetch() -> pd.DataFrame:
                tkr = yf.Ticker(ticker)
                return tkr.history(
                    start=start.isoformat(), end=end.isoformat(), timeout=10
                )

            df: pd.DataFrame= await _run_with_timeout(
                asyncio.to_thread(_blocking_fetch)
            )
            if df.empty:
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
                        date=price_date,
                        open=round(float(row.get("open", 0) or 0), 4),
                        close=round(float(row.get("close",0) or 0), 4),
                        high=round(float(row.get("high", 0) or 0), 4),
                        low=round(float(row.get("low", 0) or 0), 4),
                        volume=int(row.get("volume", 0) or 0),
                    )
                )
            return prices

        except asyncio.TimeoutError:
            # zaman aşımı — tekrar deneme yapma
            return []
        except Exception as exc:
            is_rate_limit = "429" in str(exc) or "Too Many Requests" in str(exc)
            if is_rate_limit and attempt < 2:
                wait = 2 ** (attempt + 1)  # 2s, 4s
                await asyncio.sleep(wait)
                continue
            return []

    return []


async def _load_from_db(
    ticker: str, db: AsyncSession, period_days: int
) -> list[StockPricePoint]:
    """DB den son 'period_days' günlük verileri çek"""
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
            date=r.price_date,
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
    """gelen fiyat listesini StockPrice tablosuna yaz (yeni olanları ekle)"""
    stmt = select(StockPrice.price_date).where(StockPrice.ticker == ticker)
    result = await db.execute(stmt)
    existing_dates = {r for r in result.scalars().all()}

    for p in prices:
        if p.date not in existing_dates:
            db.add(
                StockPrice(
                    ticker=ticker,
                    price_date=p.date,
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
    şirket bilgisini DB den döndür; yoksa yfinance dan çek ve kaydet
    rate-limit (429) durumunda 3 kez yeniden dener
    """
    company =await db.get(Company, ticker)
    if company and company.market_cap:
        return company

    for attempt in range(3):
        try:
            def _blocking_fetch() -> dict:
                return yf.Ticker(ticker).get_info()

            info = await _run_with_timeout(asyncio.to_thread(_blocking_fetch))

            name= info.get("longName") or info.get("shortName") or ticker
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
            break  # basarili

        except asyncio.TimeoutError:
            # zaman aşımı — DB'deki mevcut veriyle dön
            break
        except Exception as exc:
            is_rate_limit = "429" in str(exc) or "Too Many Requests" in str(exc)
            if is_rate_limit and attempt < 2:
                wait = 2 ** (attempt + 1)  # 2s, 4s
                await asyncio.sleep(wait)
                continue
            break

    return company


async def search_companies(query: str, db: AsyncSession) -> list[Company]:
    """ticker veya şirket adına göre DBde arama yap."""
    q = f"%{query.lower()}%"
    stmt = select(Company).where(
        (Company.ticker.ilike(q)) | (Company.name.ilike(q))
    ).limit(20)
    result= await db.execute(stmt)
    return result.scalars().all()