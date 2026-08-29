import os
from urllib.parse import urlparse
from sqlalchemy import create_engine, Column, String, Date, Float, BigInteger, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

def _parse_database_url(url: str) -> dict:
    parsed = urlparse(url)
    return {
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "dbname": parsed.path.lstrip("/"),
    }

if os.getenv("DATABASE_URL"):
    db_config = _parse_database_url(os.getenv("DATABASE_URL"))
    DB_USER = db_config["user"]
    DB_PASSWORD = db_config["password"]
    DB_HOST = db_config["host"]
    DB_PORT = str(db_config["port"])
    DB_NAME = db_config["dbname"]
else:
    DB_USER = os.getenv("POSTGRES_USER", "portfolio_admin")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "secure_portfolio_pwd_2026")
    DB_NAME = os.getenv("POSTGRES_DB", "portfolio_db")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db_session():
    return SessionLocal()
