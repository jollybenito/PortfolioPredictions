from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from src.domain.services.hrp_optimizer import RiskTargetedHRP
from src.domain.services.mean_variance_optimizer import MeanVarianceOptimizer
from src.domain.services.political_portfolio import PoliticalCopyPortfolio
from src.domain.services.macro_stability_engine import SovereignStabilityEngine
from src.domain.models.country_stability import SovereignPillars
from src.ports.repositories import StockPriceRepository

from src.domain.models.stock_metadata import get_metadata

class PortfolioCalculationUseCase:
    """
    Application Service that allows web app users to:
    1. Input investment budget ($200 to $999,999,999)
    2. Select a portfolio strategy ('mean_variance', 'min_variance', 'hrp', 'political', 'sovereign_stability')
    3. Adjust risk tolerance level (low, medium, high / continuous target)
    4. Mass-exclude stock groups (by Country, Sector, Exchange) and individual tickers dynamically
    5. Instantly recalculate portfolio percentage allocations, monetary capital distributions ($), and expected dollar returns
    """
    MIN_BUDGET = 200.0
    MAX_BUDGET = 999_999_999.0

    def __init__(self, stock_repo: StockPriceRepository):
        self.stock_repo = stock_repo
        self.hrp_service = RiskTargetedHRP()
        self.mean_var_service = MeanVarianceOptimizer()
        self.political_service = PoliticalCopyPortfolio()
        self.sovereign_engine = SovereignStabilityEngine()

    def calculate_custom_portfolio(
        self,
        strategy: str,
        budget: float = 1000.0,
        risk_level: float = 15.0,  # Numeric risk target percentage (e.g., 5.0% to 35.0%)
        excluded_tickers: Optional[List[str]] = None,
        excluded_countries: Optional[List[str]] = None,
        excluded_sectors: Optional[List[str]] = None,
        excluded_exchanges: Optional[List[str]] = None,
        max_pe_ratio: Optional[float] = None,
        metric: str = "sharpe"  # "sharpe", "sortino", or "treynor"
    ) -> Dict:
        # Validate budget boundaries
        if budget < self.MIN_BUDGET or budget > self.MAX_BUDGET:
            raise ValueError(f"Investment budget must be between ${self.MIN_BUDGET:,.2f} and ${self.MAX_BUDGET:,.2f} USD.")

        # Ensure risk_level is a float (handling legacy string inputs like "medium")
        if isinstance(risk_level, str):
            risk_map = {"low": 8.0, "medium": 15.0, "high": 25.0}
            target_risk_pct = risk_map.get(risk_level.lower(), 15.0)
        else:
            target_risk_pct = float(risk_level)

        # 1. Fetch historical returns dataframe
        returns_df = self.stock_repo.get_returns_df()

        if returns_df.empty:
            raise ValueError("No price data available to calculate portfolio.")

        # 2. Group & Individual Ticker Exclusion Logic
        excluded_set = set(t.upper().strip() for t in (excluded_tickers or []))
        excluded_countries_set = set(c.upper().strip() for c in (excluded_countries or []))
        excluded_sectors_set = set(s.upper().strip() for s in (excluded_sectors or []))
        excluded_exchanges_set = set(e.upper().strip() for e in (excluded_exchanges or []))

        valid_columns = []
        for ticker in returns_df.columns:
            meta = get_metadata(ticker)
            if ticker.upper() in excluded_set:
                continue
            if meta.country.upper() in excluded_countries_set:
                continue
            if meta.sector.upper() in excluded_sectors_set:
                continue
            if meta.exchange.upper() in excluded_exchanges_set:
                continue
            
            # P/E Ratio Exclusion Logic
            if max_pe_ratio is not None and max_pe_ratio > 0:
                # If ticker has no P/E or is None, treat it as an extreme case (= infinity / exceeding max_pe_ratio)
                pe_val = meta.pe_ratio
                if pe_val is None or pe_val > max_pe_ratio:
                    continue  # Exclude stock as extreme P/E case

            valid_columns.append(ticker)

        returns_df = returns_df[valid_columns]

        if returns_df.shape[1] < 2:
            raise ValueError("At least 2 assets are required after exclusions to construct a portfolio.")

        weights = {}

        # 3. Strategy Calculation Logic
        if strategy == "hrp":
            # Map target volatility percentage (5% - 35%) to cluster exponent gamma (0.2 - 3.0)
            # Lower risk target => higher gamma (more penalization of volatile clusters)
            gamma = float(np.clip(30.0 / target_risk_pct, 0.2, 3.5))
            weights = self.hrp_service.optimize(returns_df, gamma=gamma)

        elif strategy in ["mean_variance", "min_variance"]:
            cov = returns_df.cov() * 252
            weights = self.mean_var_service.optimize(returns_df, cov)

        elif strategy == "political":
            dummy_signals = pd.DataFrame([
                {"ticker": col, "signal": "BUY", "net_signal_value": np.random.uniform(0.5, 2.0)}
                for col in returns_df.columns[:10]
            ])
            w_df = self.political_service.generate_copy_weights(dummy_signals)
            weights = dict(zip(w_df['ticker'], w_df['weight']))

        elif strategy in ["sovereign_stability", "macro_stability"]:
            # Model #5: Sovereign Stability Engine
            # Baseline HRP allocation tilted by Country SSGI Scores
            base_w = self.hrp_service.optimize(returns_df, gamma=1.0)

            # Sample Sovereign Pillar Scores for US and China
            us_pillars = SovereignPillars(
                fiscal_fidelity=85.0,
                actual_vs_budget_ratio=1.12,  # 112% spend (mild overrun penalty)
                popular_support=78.0,
                conflict_invasion_risk=90.0   # Low invasion risk
            )
            cn_pillars = SovereignPillars(
                fiscal_fidelity=70.0,
                actual_vs_budget_ratio=1.45,  # 145% spend (higher overrun penalty)
                popular_support=65.0,
                conflict_invasion_risk=60.0   # Moderate regional tension risk
            )

            us_score = self.sovereign_engine.compute_country_stability("US", "United States", us_pillars)
            cn_score = self.sovereign_engine.compute_country_stability("CN", "China", cn_pillars)

            country_scores = {"US": us_score, "CN": cn_score}

            # Map tickers to countries (.SS and .SZ are China, rest US)
            ticker_map = {col: "CN" if (".SS" in col or ".SZ" in col) else "US" for col in returns_df.columns}

            # Apply country stability multiplier tilting
            weights = self.sovereign_engine.apply_stability_tilting(base_w, ticker_map, country_scores)

        else:
            n = len(returns_df.columns)
            weights = {col: 1.0 / n for col in returns_df.columns}

        # 4. Compute Expected Return & Volatility metrics
        w_series = pd.Series(weights).fillna(0)
        common = returns_df.columns.intersection(w_series.index)
        w_series = w_series[common]
        r_slice = returns_df[common]

        port_returns = r_slice.dot(w_series)
        annualized_return = float(port_returns.mean() * 252)
        annualized_volatility = float(port_returns.std() * np.sqrt(252))

        # --- Risk-Adjusted Ratio Selection ---
        risk_free_rate = 0.0  # Assume 0 for simplicity; can be parameterized later

        # Sharpe Ratio: excess return / total volatility
        sharpe_ratio = float((annualized_return - risk_free_rate) / annualized_volatility) if annualized_volatility != 0 else 0.0

        # Sortino Ratio: excess return / downside deviation
        downside_returns = port_returns[port_returns < 0]
        downside_std = float(downside_returns.std() * np.sqrt(252)) if len(downside_returns) > 0 else 0.0
        sortino_ratio = float((annualized_return - risk_free_rate) / downside_std) if downside_std != 0 else 0.0

        # Treynor Ratio: excess return / beta (relative to equal-weight market proxy)
        market_returns = r_slice.mean(axis=1)  # Equal-weight market proxy
        cov_with_market = port_returns.cov(market_returns)
        market_var = market_returns.var()
        beta = float(cov_with_market / market_var) if market_var != 0 else 1.0
        treynor_ratio = float((annualized_return - risk_free_rate) / beta) if beta != 0 else 0.0

        # Select the requested metric
        ratio_values = {
            "sharpe": round(sharpe_ratio, 4),
            "sortino": round(sortino_ratio, 4),
            "treynor": round(treynor_ratio, 4)
        }
        selected_ratio_value = ratio_values.get(metric, ratio_values["sharpe"])

        # Filter out 0 weights for frontend display and compute dollar allocation per asset
        active_weights = {k: round(float(v), 6) for k, v in weights.items() if v > 0.0001}
        dollar_allocations = {k: round(float(v) * budget, 2) for k, v in active_weights.items()}

        expected_annual_dollar_gain = round(budget * annualized_return, 2)

        return {
            "strategy": strategy,
            "budget": round(budget, 2),
            "risk_level": risk_level,
            "excluded_tickers": excluded_tickers or [],
            "metrics": {
                "expected_return_pct": round(annualized_return * 100, 2),
                "expected_annual_gain_usd": expected_annual_dollar_gain,
                "volatility_pct": round(annualized_volatility * 100, 2),
                "sharpe_ratio": round(sharpe_ratio, 4),
                "sortino_ratio": round(sortino_ratio, 4),
                "treynor_ratio": round(treynor_ratio, 4),
                "beta": round(beta, 4),
                "selected_metric": metric,
                "selected_ratio_value": selected_ratio_value
            },
            "allocations_pct": active_weights,
            "allocations_usd": dollar_allocations
        }
