import enum
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ReportTime(str, enum.Enum):
    PRE_MARKET = "pre_market"
    POST_MARKET = "post_market"
    UNKNOWN = "unknown"


class Sentiment(str, enum.Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class EarningsEvent(Base):
    __tablename__ = "earnings_events"
    __table_args__ = (
        UniqueConstraint("ticker", "report_date", name="uq_ticker_report_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    report_date = Column(Date, nullable=False, index=True)
    report_time = Column(Enum(ReportTime), default=ReportTime.UNKNOWN)
    fiscal_quarter = Column(String(20), nullable=True)
    eps_estimate = Column(Float, nullable=True)
    revenue_estimate = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    analyses = relationship("EarningsAnalysis", back_populates="earnings_event")


class EarningsAnalysis(Base):
    __tablename__ = "earnings_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    earnings_event_id = Column(
        Integer, ForeignKey("earnings_events.id"), nullable=False
    )
    eps_estimate = Column(Float, nullable=True)
    eps_actual = Column(Float, nullable=True)
    eps_surprise_pct = Column(Float, nullable=True)
    revenue_estimate = Column(Float, nullable=True)
    revenue_actual = Column(Float, nullable=True)
    revenue_surprise_pct = Column(Float, nullable=True)
    guidance_summary = Column(Text, nullable=True)
    sentiment = Column(Enum(Sentiment), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    price_reaction_pct = Column(Float, nullable=True)
    raw_analysis = Column(JSONB, nullable=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    earnings_event = relationship("EarningsEvent", back_populates="analyses")
