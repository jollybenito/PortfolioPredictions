from datetime import date
from typing import List, Optional
import pandas as pd
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.domain.models.stock_price import StockPrice as DomainStockPrice, DelistedTicker as DomainDelistedTicker
from src.ports.repositories import StockPriceRepository, DelistedTickerRepository
from database import StockPrice as DBStockPrice, DelistedTicker as DBDelistedTicker, engine, get_db_session

class SQLStockPriceRepository(StockPriceRepository):
    def __init__(self, session_factory=get_db_session):
        self.session_factory = session_factory

    def get_latest_date(self, ticker: str) -> Optional[date]:
        session: Session = self.session_factory()
        try:
            latest = session.query(func.max(DBStockPrice.date)).filter(DBStockPrice.ticker == ticker).scalar()
            return latest
        finally:
            session.close()

    def save_stock_prices(self, prices: List[DomainStockPrice]) -> int:
        if not prices:
            return 0
        df = pd.DataFrame([p.__dict__ for p in prices])
        df.to_sql('stock_prices', engine, if_exists='append', index=False, method='multi')
        return len(prices)

    def get_returns_df(self) -> pd.DataFrame:
        session: Session = self.session_factory()
        try:
            query = session.query(DBStockPrice.ticker, DBStockPrice.date, DBStockPrice.close)
            df = pd.read_sql(query.statement, session.bind)
            pivoted = df.pivot(index='date', columns='ticker', values='close')
            returns = pivoted.pct_change().dropna()
            return returns
        finally:
            session.close()

    def purge_tickers(self, tickers: List[str]) -> None:
        if not tickers:
            return
        with engine.connect() as conn:
            formatted_tickers = ", ".join([f"'{t}'" for t in tickers])
            conn.execute(text(f"DELETE FROM stock_prices WHERE ticker IN ({formatted_tickers})"))
            conn.execute(text(f"DELETE FROM delisted_tickers WHERE ticker IN ({formatted_tickers})"))
            conn.commit()

class SQLDelistedTickerRepository(DelistedTickerRepository):
    def __init__(self, session_factory=get_db_session):
        self.session_factory = session_factory

    def get_all(self) -> List[str]:
        session: Session = self.session_factory()
        try:
            results = session.query(DBDelistedTicker.ticker).all()
            return [r[0] for r in results]
        finally:
            session.close()

    def add(self, delisted: DomainDelistedTicker) -> None:
        session: Session = self.session_factory()
        try:
            db_item = DBDelistedTicker(ticker=delisted.ticker, reason=delisted.reason, date_added=delisted.date_added)
            session.merge(db_item)
            session.commit()
        finally:
            session.close()
