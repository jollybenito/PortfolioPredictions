"""
CSV-based StockPriceRepository adapter for cloud deployments (e.g., Streamlit Cloud)
where PostgreSQL is not available. Reads returns directly from returns.csv.
"""
from datetime import date
from typing import List, Optional
import os
import pandas as pd
import numpy as np

from src.domain.models.stock_price import StockPrice, DelistedTicker
from src.ports.repositories import StockPriceRepository


class CSVStockPriceRepository(StockPriceRepository):
    """Lightweight repository that reads pre-computed log returns from a CSV file."""

    def __init__(self, csv_path: str = "returns.csv"):
        self.csv_path = csv_path
        self._returns_df: Optional[pd.DataFrame] = None

    def _load(self) -> pd.DataFrame:
        if self._returns_df is None:
            if not os.path.exists(self.csv_path):
                raise FileNotFoundError(f"Returns CSV not found at: {self.csv_path}")
            self._returns_df = pd.read_csv(self.csv_path, index_col=0, parse_dates=True)
        return self._returns_df

    def get_latest_date(self, ticker: str) -> Optional[date]:
        df = self._load()
        if ticker in df.columns:
            return df.index[-1].date() if hasattr(df.index[-1], 'date') else None
        return None

    def save_stock_prices(self, prices: List[StockPrice]) -> int:
        raise NotImplementedError("CSVStockPriceRepository is read-only for cloud deployments.")

    def get_returns_df(self) -> pd.DataFrame:
        return self._load()

    def purge_tickers(self, tickers: List[str]) -> None:
        raise NotImplementedError("CSVStockPriceRepository is read-only for cloud deployments.")
