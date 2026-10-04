from datetime import datetime, date
from sqlalchemy import BigInteger, Boolean, String, Float, Integer, Date, DateTime, Text, ForeignKey, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Company(Base):
    __tablename__ ="companies"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str | None]= mapped_column(String(100), nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    approvals: Mapped[list["DrugApproval"]]= relationship(back_populates="company")
    stock_prices: Mapped[list["StockPrice"]] = relationship(back_populates="company")


class DrugApproval(Base):
    __tablename__ = "drug_approvals"

    # deterministic key: "{ticker}-{application_number}-{submission_type}-{submission_number}"
    # (ticker included so co-marketed drugs get one row per company); unique as the primary key
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(10), ForeignKey("companies.ticker"))
    drug_name: Mapped[str] = mapped_column(String(200))
    brand_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approval_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    application_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # NDA/BLA/sNDA
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)  # Approved / Rejected / Pending
    indication: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    company: Mapped["Company"] = relationship(back_populates="approvals")

class StockPrice(Base):
    __tablename__  ="stock_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("companies.ticker"))
    price_date: Mapped[date] = mapped_column(Date)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float |None]= mapped_column(Float, nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="stock_prices")


class SecFiling(Base):
    """8-K / 6-K filing text, input for the catalyst extraction step"""
    __tablename__ ="sec_filings"

    accession_number: Mapped[str] = mapped_column(String(25), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    form: Mapped[str] = mapped_column(String(10))  # 8-K / 6-K
    items: Mapped[str | None]= mapped_column(String(100), nullable=True)  # e.g. "7.01,9.01"
    filed_date: Mapped[date] = mapped_column(Date)
    url: Mapped[str] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class Catalyst(Base):
    """upcoming / recent event extracted from a  sec filing by the llm"""
    __tablename__ = "catalysts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] =mapped_column(String(10), index=True)
    accession_number: Mapped[str] = mapped_column(
        String(25), ForeignKey("sec_filings.accession_number", ondelete="CASCADE"), index=True
    )
    filing_url: Mapped[str] = mapped_column(String(500))
    # pdufa / adcom / approval / crl / regulatory_submission / topline_readout / trial_start / other
    event_type: Mapped[str] = mapped_column(String(30))
    drug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    indication: Mapped[str | None] = mapped_column(String(300), nullable=True)
    date_text: Mapped[str | None] = mapped_column(String(100), nullable=True)  # as written, e.g. "Q1 2027"
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # first day of the period
    date_precision: Mapped[str] = mapped_column(String(10))  # day / month / quarter / half / year / none
    summary: Mapped[str]=mapped_column(Text)
    source_quote: Mapped[str] = mapped_column(Text)
    # cross-model voting: how many providers found it, out of those that read the filing
    votes: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    models_total: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    agreed_by: Mapped[str] = mapped_column(String(100), default="gemini", server_default="gemini")  # comma-separated provider names
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(200))
    params_hash: Mapped[str] = mapped_column(String(64))
    data_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    expires_at: Mapped[datetime]= mapped_column(DateTime(timezone=True))