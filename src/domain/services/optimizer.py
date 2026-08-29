from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict

from src.domain.models.portfolio import PortfolioAllocation

class PortfolioOptimizer(ABC):
    @abstractmethod
    def optimize(self, returns_df: pd.DataFrame, cov_matrix: pd.DataFrame) -> Dict[str, float]:
        pass
