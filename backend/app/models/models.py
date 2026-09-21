from datetime import datetime, date
from sqlalchemy import String, Float, Integer, Date, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Company(Base):
    __tablename__ ="companies"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str | None]= mapped_column(String(100), nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    approvals: Mapped[list["DrugApproval"]]= relationship(back_populates="company")
    stock_prices: Mapped[list["StockPrice"]] = relationship(back_populates="company")


class DrugApproval(Base):
    __tablename__ = "drug_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(10), ForeignKey("companies.ticker"))
    drug_name: Mapped[str] = mapped_column(String(200))
    brand_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approval_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    application_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # NDA/BLA/sNDA
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)  # Approved / Rejected / Pending
    indication: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

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
    volume: Mapped[int | None] = mapped_column(Integer,nullable=True)

    company: Mapped["Company"] = relationship(back_populates="stock_prices")


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(200))
    params_hash: Mapped[str] = mapped_column(String(64))
    data_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    expires_at: Mapped[datetime]= mapped_column(DateTime)