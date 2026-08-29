from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional
import pandas as pd

from src.domain.models.stock_price import StockPrice, DelistedTicker
from src.domain.models.portfolio import PortfolioAllocation, StrategyMetrics

class StockPriceRepository(ABC):
    @abstractmethod
    def get_latest_date(self, ticker: str) -> Optional[date]:
        pass

    @abstractmethod
    def save_stock_prices(self, prices: List[StockPrice]) -> int:
        pass

    @abstractmethod
    def get_returns_df(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def purge_tickers(self, tickers: List[str]) -> None:
        pass

class DelistedTickerRepository(ABC):
    @abstractmethod
    def get_all(self) -> List[str]:
        pass

    @abstractmethod
    def add(self, delisted: DelistedTicker) -> None:
        pass

class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_historical_prices(self, ticker: str, start_date: str, end_date: str) -> List[StockPrice]:
        pass

    @abstractmethod
    def check_delisted(self, ticker: str) -> bool:
        pass

class PortfolioRepository(ABC):
    @abstractmethod
    def save_allocation(self, allocation: PortfolioAllocation) -> None:
        pass

    @abstractmethod
    def get_allocation(self, portfolio_type: str) -> Optional[PortfolioAllocation]:
        pass
