"""
pandas-based analysis service

Two main calculations:
  1. Impact Analysis - stock impact in the +-30 days around an FDA approval
  2. Momentum Score - market expectation index over the 30 days before approval
"""
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import DrugApproval, StockPrice
from app.schemas.schemas import (
    ImpactAnalysisOut,
    MomentumScoreOut,
    StockPricePoint,
)
from app.services.cache_service import get_cached, set_cached
from app.services.stock_service import get_stock_history


# helpers
async def _price_series(ticker: str, db: AsyncSession) -> pd.Series:
    """
    Return all historical closes for a ticker as a pandas Series.
    index: date, values: close.
    """
    stmt = (
        select(StockPrice.price_date, StockPrice.close)
        .where(StockPrice.ticker == ticker)
        .order_by(StockPrice.price_date)
    )
    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        # no rows in the DB yet — fetch from yfinance
        hist = await get_stock_history(ticker, db, period_days=730)
        rows = [(p.price_date, p.close) for p in hist.prices]

    if not rows:
        return pd.Series(dtype=float)

    dates, closes = zip(*rows)
    return pd.Series(list(closes), index=pd.to_datetime(list(dates)))


def _avg_price_in_window(
    series:pd.Series, center: date, days_before: bool, window: int
) -> float | None:
    """Average close over the 'window' days before/after the center date."""
    center_ts = pd.Timestamp(center)
    if days_before:
        mask = (series.index < center_ts) & (
            series.index >= center_ts - pd.Timedelta(days=window)
        )
    else:
        mask= (series.index > center_ts) & (
            series.index <= center_ts + pd.Timedelta(days=window)
        )
    subset = series[mask]
    return round(float(subset.mean()), 4) if not subset.empty else None


# impact analysis
async def get_impact_analysis(
    ticker: str,
    db: AsyncSession,
    window_days: int = 30,
) -> list[ImpactAnalysisOut]:
    """
    Compute the +-window_days stock impact of every FDA approval for a ticker.
    """
    # v2: StockPricePoint.date -> price_date; old entries can't be parsed
    cache_key = "impact_analysis_v2"
    params = {"ticker": ticker, "window": window_days}

    cached =await get_cached(db, cache_key, params)
    if cached is not None:
        return [ImpactAnalysisOut(**item) for item in cached]

    # load approval records
    stmt = select(DrugApproval).where(
        DrugApproval.company_id == ticker,
        DrugApproval.approval_date.isnot(None),
        DrugApproval.status == "Approved",
    )
    result = await db.execute(stmt)
    approvals = result.scalars().all()

    if not approvals:
        return []

    series= await _price_series(ticker, db)
    if series.empty:
        return []

    outputs: list[ImpactAnalysisOut] = []
    for appr in approvals:
        event_date = appr.approval_date
        pre_avg = _avg_price_in_window(series, event_date, days_before=True, window=window_days)
        post_avg =_avg_price_in_window(series, event_date, days_before=False, window=window_days)

        pct_change: float | None = None
        if pre_avg and post_avg and pre_avg > 0:
            pct_change = round((post_avg - pre_avg) / pre_avg * 100, 2)

        center_ts = pd.Timestamp(event_date)
        pre_mask = (series.index < center_ts) & (
            series.index >= center_ts - pd.Timedelta(days=window_days)
        )
        post_mask= (series.index > center_ts) & (
            series.index <= center_ts + pd.Timedelta(days=window_days)
        )

        pre_prices = [
            StockPricePoint(price_date=ts.date(), close=round(v, 4))
            for ts, v in series[pre_mask].items()
        ]
        post_prices = [
            StockPricePoint(price_date=ts.date(), close=round(v, 4))
            for ts, v in series[post_mask].items()
        ]

        outputs.append(
            ImpactAnalysisOut(
                ticker=ticker,
                drug_name=appr.drug_name,
                event_date=event_date,
                pre_avg_price=pre_avg,
                post_avg_price=post_avg,
                pct_change=pct_change,
                window_days=window_days,
                pre_prices=pre_prices,
                post_prices=post_prices,
            )
        )

    # write to cache
    await set_cached(
        db, cache_key, params, [o.model_dump() for o in outputs]
    )
    return outputs


#momentum score
def _interpret_momentum(momentum_pct: float) -> str:
    """Turn a momentum percentage into a label."""
    if momentum_pct >= 15:
        return "Piyasa onayı güçlü bekliyordu (yüksek momentum)"
    elif momentum_pct >= 5:
        return "Piyasa onayı ılımlı bekliyordu"
    elif momentum_pct >= -5:
        return "Nötr; piyasa beklentisi belirsizdi"
    elif momentum_pct >= -15:
        return "Piyasa temkinliydi; olası ret beklentisi"
    else:
        return "Sürpriz onay — piyasa ret bekliyordu (düşük momentum)"


async def get_momentum_score(
    ticker: str,
    event_date : date,
    db: AsyncSession,
) -> MomentumScoreOut:
    """
    formula: momentum_pct = (price[T-1] - price[T-30]) / price[T-30] × 100
    T = FDA approval/decision date
    """
    cache_key = "momentum_score"
    params = {"ticker": ticker, "event_date": str(event_date)}

    cached = await get_cached(db, cache_key, params)
    if cached is not None:
        return MomentumScoreOut(**cached)

    series = await _price_series(ticker, db)

    t_minus_30_price: float | None = None
    t_minus_1_price: float | None = None
    momentum_pct: float | None = None

    if not series.empty:
        event_ts = pd.Timestamp(event_date)

        # t-30: latest close at least ~30 days before the event
        window_30 = series[
            series.index <= event_ts - pd.Timedelta(days=28)
        ]
        if not window_30.empty:
            t_minus_30_price = round(float(window_30.iloc[-1]), 4)

        # t-1: latest close before the event date
        window_1 = series[series.index < event_ts]
        if not window_1.empty:
            t_minus_1_price = round(float(window_1.iloc[-1]), 4)

        if t_minus_30_price and t_minus_1_price and t_minus_30_price > 0:
            momentum_pct= round(
                (t_minus_1_price - t_minus_30_price) / t_minus_30_price * 100, 2
            )

    result = MomentumScoreOut(
        ticker=ticker,
        event_date=event_date,
        t_minus_30_price=t_minus_30_price,
        t_minus_1_price=t_minus_1_price,
        momentum_pct=momentum_pct,
        interpretation =_interpret_momentum(momentum_pct) if momentum_pct is not None else None,
    )

    await set_cached(db, cache_key, params, result.model_dump())
    return result


async def get_all_momentum_scores(
    ticker: str, db: AsyncSession
) -> list[MomentumScoreOut]:
    """Compute momentum scores for all approved FDA events of a ticker."""
    stmt= select(DrugApproval).where(
        DrugApproval.company_id == ticker,
        DrugApproval.approval_date.isnot(None),
        DrugApproval.status == "Approved",
    )
    result = await db.execute(stmt)
    approvals = result.scalars().all()

    scores = []
    for appr in approvals:
        score =await get_momentum_score(ticker, appr.approval_date, db)
        scores.append(score)
    return scores
