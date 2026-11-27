from typing import Dict

import pandas as pd
from pypfopt.efficient_frontier import EfficientFrontier


class MinimumVarianceOptimizer:
    """Long-only global minimum-variance optimizer."""

    def __init__(self, min_weight: float = 0.002):
        self.min_weight = min_weight

    def optimize(self, cov_matrix: pd.DataFrame) -> Dict[str, float]:
        covariance = cov_matrix.replace([float("inf"), float("-inf")], pd.NA).dropna(axis=0).dropna(axis=1)
        covariance = covariance.loc[covariance.index.intersection(covariance.columns),
                                    covariance.index.intersection(covariance.columns)]
        if covariance.empty:
            raise ValueError("No valid assets available for minimum-variance optimization.")

        frontier = EfficientFrontier(None, covariance)
        frontier.min_volatility()
        weights = pd.Series(frontier.clean_weights(cutoff=self.min_weight), dtype=float)
        weights = weights[weights > 0]
        total_weight = float(weights.sum())
        if total_weight <= 0:
            raise ValueError("Minimum-variance optimization produced no investable weights.")
        return (weights / total_weight).to_dict()
