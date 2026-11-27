import pandas as pd
import numpy as np
from pypfopt.efficient_frontier import EfficientFrontier
from pypfopt import expected_returns
from typing import Dict

from src.domain.services.optimizer import PortfolioOptimizer

class MeanVarianceOptimizer(PortfolioOptimizer):
    def __init__(self, min_weight: float = 0.002):
        self.min_weight = min_weight

    def optimize(self, returns_df: pd.DataFrame, cov_matrix: pd.DataFrame) -> Dict[str, float]:
        mu = expected_returns.mean_historical_return(returns_df, returns_data=True, frequency=252)
        mu = mu.replace([np.inf, -np.inf], np.nan).dropna()
        common_tickers = mu.index.intersection(cov_matrix.index)
        mu = mu[common_tickers]
        S = cov_matrix.loc[common_tickers, common_tickers]

        ef = EfficientFrontier(mu, S)
        ef.max_sharpe()
        cleaned_weights = pd.Series(ef.clean_weights(cutoff=self.min_weight), dtype=float)
        cleaned_weights = cleaned_weights[cleaned_weights > 0]
        total_weight = float(cleaned_weights.sum())
        if total_weight <= 0:
            raise ValueError("Mean-variance optimization produced no investable weights.")
        return (cleaned_weights / total_weight).to_dict()
