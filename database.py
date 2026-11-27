import os
from sqlalchemy import create_engine, Column, String, Date, Float, BigInteger, UniqueConstraint
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

def _resolved_host(host: str) -> bool:
    return bool(host and not any(char in host for char in "{}$<> \t\r\n"))


def _database_url_from_environment():
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        try:
            parsed_url = make_url(configured_url)
        except Exception:
            parsed_url = None
        if parsed_url is not None and _resolved_host(parsed_url.host):
            if parsed_url.drivername == "postgres":
                parsed_url = parsed_url.set(drivername="postgresql")
            return parsed_url

    pg_user = os.getenv("PGUSER") or os.getenv("POSTGRES_USER", "portfolio_admin")
    pg_password = os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD")
    pg_database = os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB", "portfolio_db")
    pg_host = os.getenv("PGHOST") or os.getenv("DB_HOST", "localhost")
    pg_port = os.getenv("PGPORT") or os.getenv("DB_PORT", "5432")

    if not _resolved_host(pg_host):
        raise ValueError("PostgreSQL host is unresolved. Set DATABASE_URL or PGHOST to an actual hostname.")
    if not pg_password:
        raise ValueError("PostgreSQL password is missing. Set PGPASSWORD or POSTGRES_PASSWORD.")

    return URL.create(
        "postgresql+psycopg2",
        username=pg_user,
        password=pg_password,
        host=pg_host,
        port=int(pg_port),
        database=pg_database,
    )


DATABASE_URL = _database_url_from_environment()

engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class StockPrice(Base):
    __tablename__ = "stock_prices"
    ticker = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    open = Column(Float)
    volume = Column(BigInteger)
    __table_args__ = (UniqueConstraint('ticker', 'date', name='uq_ticker_date'),)

class FXRate(Base):
    __tablename__ = "fx_rates"
    currency = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    usd_per_unit = Column(Float, nullable=False)

class PortfolioWeight(Base):
    __tablename__ = "portfolio_weights"
    portfolio_type = Column(String, primary_key=True)
    ticker = Column(String, primary_key=True)
    weight = Column(Float)
    date = Column(Date, primary_key=True)

class CovarianceMatrix(Base):
    __tablename__ = "covariance_estimates"
    method = Column(String, primary_key=True)  # 'sample' or 'ledoit_wolf'
    ticker_a = Column(String, primary_key=True)
    ticker_b = Column(String, primary_key=True)
    value = Column(Float)
    date = Column(Date, primary_key=True)

class ExpectedReturn(Base):
    __tablename__ = "expected_returns"
    ticker = Column(String, primary_key=True)
    value = Column(Float)
    date = Column(Date, primary_key=True)

class SenatorTrade(Base):
    __tablename__ = "senator_trades"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    senator = Column(String)
    ticker = Column(String)
    date = Column(Date)
    type = Column(String) # 'Purchase', 'Sale Full', etc.
    amount_midpoint = Column(Float)

class SenatorScore(Base):
    __tablename__ = "senator_scores"
    senator = Column(String, primary_key=True)
    historical_return = Column(Float)
    consistency_factor = Column(Float)
    activity_factor = Column(Float)
    final_score = Column(Float)
    last_updated = Column(Date)

class StockSignal(Base):
    __tablename__ = "stock_signals"
    ticker = Column(String, primary_key=True)
    signal = Column(String) # 'BUY', 'HOLD', 'EXIT'
    net_signal_value = Column(Float)
    risk_score = Column(Float)
    date = Column(Date, primary_key=True)

class MarketSentiment(Base):
    __tablename__ = "market_sentiment"
    ticker = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    news_sentiment = Column(Float)
    news_buzz = Column(Float)
    reddit_mentions = Column(BigInteger)
    reddit_score = Column(Float)
    composite_score = Column(Float)

class DelistedTicker(Base):
    __tablename__ = "delisted_tickers"
    ticker = Column(String, primary_key=True)
    reason = Column(String)
    date_added = Column(Date)

class ETLMetadata(Base):
    __tablename__ = "etl_metadata"
    key = Column(String, primary_key=True)
    value = Column(String)
    updated_at = Column(Date)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db_session():
    return SessionLocal()
