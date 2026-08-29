import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform
from typing import Dict, List, Tuple

class RiskTargetedHRP:
    """
    Hierarchical Risk Parity (HRP) with Risk-Targeted Asset/Cluster Tilting.
    
    The gamma parameter controls cluster risk exponent:
    - gamma > 1.0 (e.g. 2.0 or higher): Conservative / High risk-aversion (heavily penalizes volatile clusters).
    - gamma = 1.0: Standard HRP (Inverse variance weighting).
    - 0.0 < gamma < 1.0 (e.g. 0.5): Aggressive / Low risk-aversion (approaches equal weighting across clusters).
    """

    def __init__(self, min_weight: float = 0.01):  # $10 min / $1000 default budget = 0.01
        self.min_weight = min_weight

    def _get_distance_matrix(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        corr = returns_df.corr()
        # Distance metric: d_ij = sqrt(0.5 * (1 - rho_ij))
        dist = np.sqrt(0.5 * (1 - corr).clip(lower=0))
        return dist, corr

    def _get_quasi_diag(self, link: np.ndarray) -> List[int]:
        # Sort items in linkage tree to preserve cluster hierarchy
        link = link.astype(int)
        sort_ix = [link[-1, 0], link[-1, 1]]
        num_items = link[-1, 3]
        while sort_ix[0] >= num_items or any(x >= num_items for x in sort_ix):
            for i, x in enumerate(sort_ix):
                if x >= num_items:
                    sort_ix[i] = link[x - num_items, 0]
                    sort_ix.insert(i + 1, link[x - num_items, 1])
                    break
        return sort_ix

    def _get_cluster_var(self, cov: pd.DataFrame, cluster_items: List[str], gamma: float) -> float:
        # Compute total cluster variance using risk exponent gamma
        cov_slice = cov.loc[cluster_items, cluster_items]
        # Equal weighting internal to sub-cluster to evaluate baseline sub-cluster variance
        w = np.ones((len(cluster_items), 1)) / len(cluster_items)
        var = np.dot(np.dot(w.T, cov_slice.values), w)[0, 0]
        return var

    def _recursive_bisection(self, cov: pd.DataFrame, sort_ix: List[str], gamma: float) -> pd.Series:
        weights = pd.Series(1.0, index=sort_ix)
        clusters = [sort_ix]

        while len(clusters) > 0:
            clusters = [c[j:k] for c in clusters for j, k in ((0, len(c) // 2), (len(c) // 2, len(c))) if len(c) > 1]
            for i in range(0, len(clusters), 2):
                c0 = clusters[i]
                c1 = clusters[i + 1]

                v0 = self._get_cluster_var(cov, c0, gamma)
                v1 = self._get_cluster_var(cov, c1, gamma)

                # Risk-Targeted Allocation with gamma parameter
                # Allocation factor alpha for cluster 0 vs cluster 1
                v0_g = v0 ** (gamma / 2.0)
                v1_g = v1 ** (gamma / 2.0)

                alpha = 1.0 - (v0_g / (v0_g + v1_g))

                weights[c0] *= alpha
                weights[c1] *= (1.0 - alpha)

        return weights

    def optimize(self, returns_df: pd.DataFrame, gamma: float = 1.0) -> Dict[str, float]:
        # Drop missing values
        returns_df = returns_df.dropna(axis=1, how='all').fillna(0)
        cov = returns_df.cov()
        dist, corr = self._get_distance_matrix(returns_df)

        # Hierarchical Linkage
        dist_condensed = squareform(dist.values, checks=False)
        link = linkage(dist_condensed, method='single')

        # Quasi-Diagonalization
        sort_ix_num = self._get_quasi_diag(link)
        sort_ix = returns_df.columns[sort_ix_num].tolist()

        # Recursive Bisection with Risk Exponent Gamma
        weights = self._recursive_bisection(cov, sort_ix, gamma)

        # Clean small weights below threshold
        weights[weights < self.min_weight] = 0
        weights = weights / weights.sum()

        return weights.to_dict()

    def generate_hrp_frontier(self, returns_df: pd.DataFrame, num_points: int = 15) -> pd.DataFrame:
        """
        Generates HRP Risk-Return Frontier across a spectrum of risk exponents (gamma values).
        gamma ranges from 0.1 (Aggressive) to 3.0 (Conservative).
        """
        gammas = np.linspace(0.1, 3.0, num_points)
        frontier_data = []

        for g in gammas:
            w_dict = self.optimize(returns_df, gamma=g)
            w = pd.Series(w_dict)
            
            # Filter returns for matched assets
            common_assets = list(set(returns_df.columns) & set(w.index))
            w = w[common_assets]
            r = returns_df[common_assets]

            port_returns = r.dot(w)
            exp_ret = port_returns.mean() * 252
            vol = port_returns.std() * np.sqrt(252)
            sharpe = exp_ret / vol if vol != 0 else 0

            frontier_data.append({
                'gamma': g,
                'expected_return': exp_ret,
                'volatility': vol,
                'sharpe_ratio': sharpe,
                'weights': w_dict
            })

        return pd.DataFrame(frontier_data)
