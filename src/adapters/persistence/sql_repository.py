from datetime import date
from typing import List, Optional
import pandas as pd
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.domain.models.stock_price import FXRate as DomainFXRate, StockPrice as DomainStockPrice, DelistedTicker as DomainDelistedTicker
from src.domain.models.currency import currency_for_ticker, prices_to_usd_returns
from src.ports.repositories import StockPriceRepository, DelistedTickerRepository
from database import FXRate as DBFXRate, StockPrice as DBStockPrice, DelistedTicker as DBDelistedTicker, engine, get_db_session

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
        rows = [price.__dict__ for price in prices]
        statement = pg_insert(DBStockPrice).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[DBStockPrice.ticker, DBStockPrice.date],
            set_={
                "close": statement.excluded.close,
                "high": statement.excluded.high,
                "low": statement.excluded.low,
                "open": statement.excluded.open,
                "volume": statement.excluded.volume,
            },
        )
        with engine.begin() as connection:
            connection.execute(statement)
        return len(prices)

    def get_returns_df(self) -> pd.DataFrame:
        session: Session = self.session_factory()
        try:
            price_query = session.query(DBStockPrice.ticker, DBStockPrice.date, DBStockPrice.close)
            price_rows = pd.read_sql(price_query.statement, session.bind)
            if price_rows.empty:
                return pd.DataFrame()
            prices = price_rows.pivot(index="date", columns="ticker", values="close").sort_index()

            currencies = {currency_for_ticker(ticker) for ticker in prices.columns} - {"USD"}
            fx_rates = pd.DataFrame()
            if currencies:
                try:
                    fx_query = session.query(DBFXRate.currency, DBFXRate.date, DBFXRate.usd_per_unit).filter(
                        DBFXRate.currency.in_(currencies)
                    )
                    fx_rows = pd.read_sql(fx_query.statement, session.bind)
                except Exception as exc:
                    raise RuntimeError("FX rate storage is not initialized. Run the market data ETL to create and populate fx_rates.") from exc
                if fx_rows.empty:
                    raise RuntimeError("No FX rates found. Run the market data ETL to populate fx_rates before calculating USD returns.")
                fx_rates = fx_rows.pivot(index="date", columns="currency", values="usd_per_unit").sort_index()

            calendar_ticker = "SPY" if "SPY" in prices.columns else "AAPL" if "AAPL" in prices.columns else None
            if calendar_ticker is None:
                raise RuntimeError("USD returns need SPY or AAPL prices to define the US trading calendar.")
            trading_calendar = prices.index[prices[calendar_ticker].notna()]
            return prices_to_usd_returns(prices, fx_rates, trading_calendar=trading_calendar)
        finally:
            session.close()

    def purge_tickers(self, tickers: List[str]) -> None:
        if not tickers:
            return
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM stock_prices WHERE ticker = ANY(:tickers)"),
                {"tickers": tickers},
            )
            conn.execute(
                text("DELETE FROM delisted_tickers WHERE ticker = ANY(:tickers)"),
                {"tickers": tickers},
            )
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


class SQLFXRateRepository:
    def __init__(self, session_factory=get_db_session):
        self.session_factory = session_factory

    def get_latest_date(self, currency: str) -> Optional[date]:
        session: Session = self.session_factory()
        try:
            return session.query(func.max(DBFXRate.date)).filter(DBFXRate.currency == currency).scalar()
        finally:
            session.close()

    def save_fx_rates(self, rates: List[DomainFXRate]) -> int:
        if not rates:
            return 0
        rows = [
            {"currency": rate.currency, "date": rate.date, "usd_per_unit": rate.usd_per_unit}
            for rate in rates
        ]
        statement = pg_insert(DBFXRate).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[DBFXRate.currency, DBFXRate.date],
            set_={"usd_per_unit": statement.excluded.usd_per_unit},
        )
        with engine.begin() as connection:
            connection.execute(statement)
        return len(rates)
