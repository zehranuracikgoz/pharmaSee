from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.schemas import (
    CompanyOut,
    SearchOut,
    SearchResultItem,
    StockHistoryOut,
    TrackedCompanyOut,
)
from app.services.stock_service import get_company_info, get_stock_history, search_companies

router = APIRouter(prefix="/stocks", tags=["Stocks"])
companies_router = APIRouter(tags=["Stocks"])


@companies_router.get(
    "/companies", response_model=list[TrackedCompanyOut], summary="Takip edilen şirketler"
)
async def tracked_companies():
    """Return config.TRACKED_TICKERS — the frontend's single source of tickers."""
    return [
        TrackedCompanyOut(ticker=ticker, name=name)
        for ticker, name in settings.TRACKED_TICKERS.items()
    ]


@router.get("/search", response_model=SearchOut, summary="Şirket arama")
async def search(
    q: str= Query(..., min_length=1, description="Ticker veya şirket adı"),
    db: AsyncSession = Depends(get_db),
):
    """Search the DB by ticker or company name."""
    companies = await search_companies(q, db)
    results = [
        SearchResultItem(ticker=c.ticker, name=c.name, sector=c.sector)
        for c in companies
    ]
    return SearchOut(results=results, query=q, total=len(results))


@router.get("/{ticker}/info", response_model=CompanyOut, summary="Şirket bilgisi")
async def company_info(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """Return company name, sector and market cap."""
    ticker = ticker.upper()
    company =await get_company_info(ticker, db)
    if not company:
        raise HTTPException(status_code=404, detail=f"{ticker} bulunamadı")
    return company


@router.get("/{ticker}/history", response_model=StockHistoryOut, summary="Hisse fiyat geçmişi")
async def stock_history(
    ticker: str,
    period_days:int = Query(default=365, ge=7, le=730, description="Kaç günlük geçmiş"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return closing prices from yfinance.
    Cached for 24 hours; served from the DB if yfinance is down.
    """
    ticker = ticker.upper()
    return await get_stock_history(ticker, db, period_days=period_days)
