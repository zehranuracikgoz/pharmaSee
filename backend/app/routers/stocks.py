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
    "/companies", response_model=list[TrackedCompanyOut], summary="Tracked companies"
)
async def tracked_companies():
    """Return config.TRACKED_TICKERS — the frontend's single source of tickers."""
    return [
        TrackedCompanyOut(ticker=ticker, name=name)
        for ticker, name in settings.TRACKED_TICKERS.items()
    ]


@router.get("/search", response_model=SearchOut, summary="Company search")
async def search(
    q: str= Query(..., min_length=1, description="Ticker or company name"),
    db: AsyncSession = Depends(get_db),
):
    """Search the DB by ticker or company name."""
    companies = await search_companies(q, db)
    results = [
        SearchResultItem(ticker=c.ticker, name=c.name, industry=c.industry)
        for c in companies
    ]
    return SearchOut(results=results, query=q, total=len(results))


@router.get("/{ticker}/info", response_model=CompanyOut, summary="Company info")
async def company_info(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """Return company name, industry and market cap."""
    ticker = ticker.upper()
    company =await get_company_info(ticker, db)
    if not company:
        raise HTTPException(status_code=404, detail=f"{ticker} not found")
    return company


@router.get("/{ticker}/history", response_model=StockHistoryOut, summary="Stock price history")
async def stock_history(
    ticker: str,
    period_days:int = Query(default=365, ge=7, le=730, description="Days of history"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return closing prices from yfinance.
    Cached for 24 hours; served from the DB if yfinance is down.
    """
    ticker = ticker.upper()
    return await get_stock_history(ticker, db, period_days=period_days)
