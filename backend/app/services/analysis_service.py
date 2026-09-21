"""
pandas tabanlı analiz servisi

İki ana hesaplama:
  1.Impact Analysis - FDA onayının +-30 günlük hisse etkisi
  2.Momentum Score - Onay öncesi 30 günlük piyasa beklenti endeksi
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


#yardımcılar
async def _price_series(ticker: str, db: AsyncSession) -> pd.Series:
    """
    ticker'ın tüm tarihsel kapanış fiyatlarını pandas series olarak döndür
    index: date, Values: close.
    """
    stmt = (
        select(StockPrice.price_date, StockPrice.close)
        .where(StockPrice.ticker == ticker)
        .order_by(StockPrice.price_date)
    )
    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        # DB de veri yoksa yfinance dan çek
        hist = await get_stock_history(ticker, db, period_days=730)
        rows = [(p.date, p.close) for p in hist.prices]

    if not rows:
        return pd.Series(dtype=float)

    dates, closes = zip(*rows)
    return pd.Series(list(closes), index=pd.to_datetime(list(dates)))


def _avg_price_in_window(
    series:pd.Series, center: date, days_before: bool, window: int
) -> float | None:
    """center tarihine göre önceki/sonraki 'window' günlük ortalama kapanış."""
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
    ticker için tüm FDA onay olaylarının +-window_days günlük hisse etkisini hesaplamak icin
    """
    cache_key = "impact_analysis"
    params = {"ticker": ticker, "window": window_days}

    cached =await get_cached(db, cache_key, params)
    if cached:
        return [ImpactAnalysisOut(**item) for item in cached]

    # onay kayıtlarını cekmek icin
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
            StockPricePoint(date=ts.date(), close=round(v, 4))
            for ts, v in series[pre_mask].items()
        ]
        post_prices = [
            StockPricePoint(date=ts.date(), close=round(v, 4))
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

    # onbellege yaz
    await set_cached(
        db, cache_key, params, [o.model_dump() for o in outputs]
    )
    return outputs


#momentum score
def _interpret_momentum(momentum_pct: float) -> str:
    """momentum yüzdesine göre yorum üret."""
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
    formül: momentum_pct = (fiyat[T-1] - fiyat[T-30]) / fiyat[T-30] × 100
    T = FDA onay/karar tarihi
    """
    cache_key = "momentum_score"
    params = {"ticker": ticker, "event_date": str(event_date)}

    cached = await get_cached(db, cache_key, params)
    if cached:
        return MomentumScoreOut(**cached)

    series = await _price_series(ticker, db)

    t_minus_30_price: float | None = None
    t_minus_1_price: float | None = None
    momentum_pct: float | None = None

    if not series.empty:
        event_ts = pd.Timestamp(event_date)

        # t-30: event tarihinden 30+ gün önceki en yakın kapanış
        window_30 = series[
            series.index <= event_ts - pd.Timedelta(days=28)
        ]
        if not window_30.empty:
            t_minus_30_price = round(float(window_30.iloc[-1]), 4)

        # t-1: event tarihinden 1+ gün önceki en yakın kapanış
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
    """ticker ın tüm onaylanmış FDA olayları için momentum skoru hesaplamak icin"""
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
