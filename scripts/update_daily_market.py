"""Refresh recent market prices and FX rates already represented in PostgreSQL."""

from datetime import datetime, timedelta, timezone
import time

from database import ETLMetadata, StockPrice, engine, get_db_session, init_db
from src.adapters.persistence.sql_repository import SQLFXRateRepository, SQLStockPriceRepository
from src.adapters.providers.yfinance_adapter import YFinanceAdapter
from src.domain.models.currency import currency_for_ticker


OVERLAP_DAYS = 7
REQUEST_DELAY_SECONDS = 1
INITIAL_FX_START_DATE = "2015-01-01"


def get_stored_tickers() -> list[str]:
    session = get_db_session()
    try:
        return sorted({row[0] for row in session.query(StockPrice.ticker).distinct().all()})
    finally:
        session.close()


def refresh_fx_rates(tickers: list[str], provider: YFinanceAdapter) -> int:
    fx_repository = SQLFXRateRepository()
    currencies = sorted({currency_for_ticker(ticker) for ticker in tickers} - {"USD"})
    end_date = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    saved_total = 0

    for currency in currencies:
        latest_date = fx_repository.get_latest_date(currency)
        start_date = (
            (latest_date - timedelta(days=OVERLAP_DAYS)).isoformat()
            if latest_date
            else INITIAL_FX_START_DATE
        )
        rates = provider.fetch_historical_fx_rates(currency, start_date, end_date)
        if not rates and latest_date is None:
            raise RuntimeError(f"No FX history exists for {currency} and the provider returned no data.")
        saved = fx_repository.save_fx_rates(rates)
        saved_total += saved
        print(f"{currency}: upserted {saved} FX observations from {start_date}.")

    return saved_total


def record_update(timestamp: datetime) -> None:
    session = get_db_session()
    try:
        session.merge(
            ETLMetadata(
                key="daily_market_update",
                value=timestamp.isoformat(),
                updated_at=timestamp.date(),
            )
        )
        session.commit()
    finally:
        session.close()


def main() -> None:
    init_db()
    tickers = get_stored_tickers()
    if not tickers:
        raise RuntimeError("stock_prices is empty. Load the initial price history before scheduling daily updates.")

    print(f"Refreshing {len(tickers)} tickers already stored in PostgreSQL.")
    provider = YFinanceAdapter()
    fx_rows = refresh_fx_rates(tickers, provider)

    stock_repository = SQLStockPriceRepository()
    end_date = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    updated_rows = 0
    no_new_rows = []
    failed_tickers = []

    for index, ticker in enumerate(tickers, start=1):
        latest_date = stock_repository.get_latest_date(ticker)
        if latest_date is None:
            no_new_rows.append(ticker)
            continue

        start_date = (latest_date - timedelta(days=OVERLAP_DAYS)).isoformat()
        try:
            prices = provider.fetch_historical_prices(ticker, start_date, end_date)
            if prices:
                updated_rows += stock_repository.save_stock_prices(prices)
                print(f"[{index}/{len(tickers)}] {ticker}: upserted {len(prices)} price rows.")
            else:
                # Normal for exchange holidays or if Yahoo has not published a new bar.
                no_new_rows.append(ticker)
                print(f"[{index}/{len(tickers)}] {ticker}: no recent price rows returned.")
        except Exception as exc:
            failed_tickers.append(ticker)
            print(f"[{index}/{len(tickers)}] {ticker}: update failed ({type(exc).__name__}).")

        if index < len(tickers):
            time.sleep(REQUEST_DELAY_SECONDS)

    if failed_tickers:
        raise RuntimeError(f"Price updates failed for {len(failed_tickers)} tickers: {', '.join(failed_tickers)}")

    timestamp = datetime.now(timezone.utc)
    record_update(timestamp)
    print(
        f"Daily market update complete at {timestamp.isoformat()}: "
        f"{updated_rows} price rows upserted, {fx_rows} FX rows upserted, "
        f"{len(no_new_rows)} tickers had no recent bar."
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
