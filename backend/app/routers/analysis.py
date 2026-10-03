from datetime import date

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Company, DrugApproval
from app.schemas.schemas import (
    CompanyProfileOut ,
    CompareOut ,
    ImpactAnalysisOut ,
    MomentumScoreOut ,
)
from app.services.analysis_service import (
    get_all_momentum_scores,
    get_impact_analysis ,
    get_momentum_score,
)
from app.services.fda_service import upsert_approvals
from app.services.stock_service import get_company_info, get_stock_history

router = APIRouter(prefix="/analysis", tags=["Analysis"])


# impact analysis
@router.get(
    "/impact/{ticker}",
    response_model=list[ImpactAnalysisOut],
    summary="FDA approval impact analysis",
)
async def impact_analysis(
    ticker: str,
    window_days: int = Query(default=30, ge=7, le=90, description="Analysis window (days)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute the +-window_days stock price impact of every FDA approval for the company.
    """
    ticker = ticker.upper()
    await upsert_approvals(ticker, db)
    results = await get_impact_analysis(ticker, db, window_days=window_days)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient approval or price data for {ticker}",
        )
    return results


# momentum score
@router.get(
    "/momentum",
    response_model=MomentumScoreOut,
    summary="Momentum score — market expectation before an FDA decision",
)
async def momentum_score(
    ticker: str = Query(..., description="Company ticker symbol (e.g. MRNA)"),
    event_date: date = Query(..., description="FDA decision date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Formula: momentum_pct = (price[T-1] − price[T-30]) / price[T-30] * 100

    High positive value -> the market expected approval.
    Negative value -> the market was cautious; the approval may have been a surprise.
    """
    ticker = ticker.upper()
    # make sure price data is in the DB first
    await get_stock_history(ticker, db, period_days=730)
    return await get_momentum_score(ticker, event_date, db)


@router.get(
    "/momentum/{ticker}/all",
    response_model=list[MomentumScoreOut],
    summary="Momentum scores for all FDA events of a company",
)
async def all_momentum_scores(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return momentum scores for all approved FDA events of the ticker.
    """
    ticker = ticker.upper()
    await upsert_approvals(ticker, db)
    await get_stock_history(ticker, db, period_days=730)
    return await get_all_momentum_scores(ticker, db)


# company profile
@router.get(
    "/profile/{ticker}",
    response_model=CompanyProfileOut,
    summary="Company profile — stock + approvals + momentum",
)
async def company_profile(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Company info, latest price, FDA approvals and momentum scores
    in a single call. Used by the company profile page.
    """
    ticker = ticker.upper()

    company = await get_company_info(ticker, db)
    if not company:
        raise HTTPException(status_code=404, detail=f"{ticker} not found")

    history = await get_stock_history(ticker, db, period_days=365)
    await upsert_approvals(ticker , db)

    latest_price:float | None = None
    price_change_1d: float | None = None
    if history.prices:
        latest_price = history.prices[-1].close
        if len(history.prices) >= 2:
            prev = history.prices[-2].close
            if prev and prev > 0:
                price_change_1d = round((latest_price - prev) / prev * 100, 2)

    stmt=select(DrugApproval).where(
        DrugApproval.company_id == ticker
    ).order_by(DrugApproval.approval_date.desc()).limit(20)
    result = await db.execute(stmt)
    approvals = result.scalars().all()

    momentum_scores = await get_all_momentum_scores(ticker, db)

    return CompanyProfileOut(
        company=company,
        latest_price=latest_price,
        price_change_pct_1d=price_change_1d,
        approvals=list(approvals),
        momentum_scores=momentum_scores,
    )


#compare
@router.get(
    "/compare",
    response_model=CompareOut,
    summary="Compare two companies",
)
async def compare(
    a: str = Query(..., description="First ticker (e.g. MRNA)"),
    b: str = Query(..., description="Second ticker (e.g. BNTX)"),
    period_days: int = Query(default=365, ge=30, le=730),
    db: AsyncSession = Depends(get_db),
):
    """
    Price history and FDA approvals of two biotech companies
    in a single call. Used by the /compare page.
    """
    ticker_a = a.upper()
    ticker_b = b.upper()

    company_a = await get_company_info(ticker_a, db)
    company_b = await get_company_info(ticker_b, db)

    history_a = await get_stock_history(ticker_a, db, period_days=period_days)
    history_b = await get_stock_history(ticker_b, db, period_days=period_days)

    await upsert_approvals(ticker_a, db)
    await upsert_approvals(ticker_b, db)

    stmt_a = select(DrugApproval).where(
        DrugApproval.company_id == ticker_a
    ).order_by(DrugApproval.approval_date.desc()).limit(10)
    stmt_b = select(DrugApproval).where(
        DrugApproval.company_id == ticker_b
    ).order_by(DrugApproval.approval_date.desc()).limit(10)

    approvals_a=(await db.execute(stmt_a)).scalars().all()
    approvals_b=(await db.execute(stmt_b)).scalars().all()

    return CompareOut(
        ticker_a=ticker_a,
        ticker_b=ticker_b,
        company_a=company_a,
        company_b=company_b,
        history_a=history_a.prices,
        history_b=history_b.prices,
        approvals_a=list(approvals_a),
        approvals_b=list(approvals_b),
    )
