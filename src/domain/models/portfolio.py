from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

@dataclass
class PortfolioAllocation:
    portfolio_type: str
    weights: Dict[str, float]
    as_of_date: date

@dataclass
class CovarianceEstimate:
    method: str  # e.g., 'sample', 'ledoit_wolf'
    matrix_df: object  # pandas DataFrame representation
    as_of_date: date

@dataclass
class StrategyMetrics:
    strategy_name: str
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
