from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass(frozen=True)
class StockPrice:
    ticker: str
    date: date
    close: float
    high: float
    low: float
    open: float
    volume: int

@dataclass(frozen=True)
class DelistedTicker:
    ticker: str
    reason: str
    date_added: date

@dataclass(frozen=True)
class FXRate:
    currency: str
    date: date
    usd_per_unit: float
