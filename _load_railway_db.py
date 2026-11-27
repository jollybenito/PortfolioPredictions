"""One-off: populate Railway Postgres with OHLCV + FX for the historical tickers.

Runs against the DATABASE_URL in the environment (the SSH tunnel to Railway).
Uses the project's own adapter and repositories, then recomputes variance.
"""

import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, engine
from src.adapters.providers.yfinance_adapter import YFinanceAdapter
from src.adapters.persistence.sql_repository import (
    SQLStockPriceRepository,
    SQLFXRateRepository,
)
from src.domain.models.currency import currency_for_ticker

START_DATE = "2015-01-01"


def historical_tickers():
    df = pd.read_csv("returns.csv", index_col=0, parse_dates=True)
    return list(df.columns)


def main():
    tickers = historical_tickers()
    end_date = datetime.now().strftime("%Y-%m-%d")
    print(f"Loading {len(tickers)} tickers {START_DATE} -> {end_date}")

    init_db()
    provider = YFinanceAdapter()
    price_repo = SQLStockPriceRepository()
    fx_repo = SQLFXRateRepository()

    # FX first (non-USD currencies only)
    currencies = sorted({currency_for_ticker(t) for t in tickers} - {"USD"})
    print(f"Syncing FX for currencies: {currencies}")
    for ccy in currencies:
        rates = provider.fetch_historical_fx_rates(ccy, "2015-01-01", end_date)
        if not rates:
            raise RuntimeError(f"No FX history for {ccy}")
        saved = fx_repo.save_fx_rates(rates)
        print(f"  {ccy}: {saved} FX rows")

    # OHLCV per ticker
    total = 0
    for i, ticker in enumerate(tickers, 1):
        prices = provider.fetch_historical_prices(ticker, START_DATE, end_date)
        if not prices:
            print(f"[{i}/{len(tickers)}] {ticker}: NO DATA (skipped)")
            continue
        saved = price_repo.save_stock_prices(prices)
        total += saved
        print(f"[{i}/{len(tickers)}] {ticker}: {saved} rows")

    print(f"Total OHLCV rows saved: {total}")


if __name__ == "__main__":
    main()