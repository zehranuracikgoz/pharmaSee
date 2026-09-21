from datetime import date, datetime
from pydantic import BaseModel


# company
class CompanyBase(BaseModel):
    ticker: str
    name: str
    sector: str | None = None
    market_cap: float | None = None
    description: str | None = None

class CompanyOut(CompanyBase):
    model_config = {"from_attributes": True}


# drug approval
class DrugApprovalOut(BaseModel):
    id: str
    company_id: str
    drug_name: str
    brand_name: str | None = None
    approval_date: date | None = None
    application_type: str | None = None
    status: str | None = None
    indication: str | None = None

    model_config = {"from_attributes": True}


#stockprice
class StockPricePoint(BaseModel):
    date: date
    open: float | None = None
    close: float
    high: float | None = None
    low: float | None = None
    volume: int | None = None


class StockHistoryOut(BaseModel):
    ticker: str
    prices: list[StockPricePoint]


# fda calender
class FDACalendarItem(BaseModel):
    company_name: str
    ticker: str | None = None
    drug_name: str
    brand_name: str | None = None
    pdufa_date: date | None = None
    application_type: str | None = None
    status: str | None = None
    indication: str | None = None

class FDACalendarOut(BaseModel):
    items:list[FDACalendarItem]
    total: int


#impact analysis
class ImpactAnalysisOut(BaseModel):
    ticker: str
    drug_name: str
    event_date: date
    pre_avg_price: float | None = None
    post_avg_price: float | None = None
    pct_change: float | None = None
    window_days : int = 30
    pre_prices: list[StockPricePoint] = []
    post_prices: list[StockPricePoint] = []


#momentum score
class MomentumScoreOut(BaseModel):
    ticker: str
    event_date: date
    t_minus_30_price: float | None= None
    t_minus_1_price: float | None = None
    momentum_pct: float | None = None
    interpretation: str | None = None  # "Piyasa onayı bekliyordu" / "Sürpriz onay" vb


# company profile
class CompanyProfileOut(BaseModel):
    company: CompanyOut
    latest_price: float | None = None
    price_change_pct_1d: float | None = None
    approvals : list[DrugApprovalOut] = []
    momentum_scores: list[MomentumScoreOut] = []


# compare
class CompareOut(BaseModel):
    ticker_a: str
    ticker_b: str
    company_a: CompanyOut | None = None
    company_b: CompanyOut | None = None
    history_a: list[StockPricePoint] = []
    history_b: list[StockPricePoint] = []
    approvals_a: list[DrugApprovalOut] = []
    approvals_b:list[DrugApprovalOut] = []


# search
class SearchResultItem(BaseModel):
    ticker: str
    name: str
    sector: str | None = None
    latest_close: float | None = None

class SearchOut(BaseModel):
    results: list[SearchResultItem]
    query: str
    total:int