from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.schemas import CompanyOut, SearchOut, SearchResultItem, StockHistoryOut
from app.services.stock_service import get_company_info, get_stock_history, search_companies

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("/search", response_model=SearchOut, summary="Şirket arama")
async def search(
    q: str= Query(..., min_length=1, description="Ticker veya şirket adı"),
    db: AsyncSession = Depends(get_db),
):
    """ticker veya şirket adına göre DB'de arama yapar."""
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
    """şirket adı, sektör ve piyasa değerini döndürmek icin"""
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
    yfinance üzerinden hisse kapanis fiyatlarını döndürür
    onbellek 24 saat geçerlidir; yfinance kesintisinde DB den servis edilir
    """
    ticker = ticker.upper()
    return await get_stock_history(ticker, db, period_days=period_days)
