import pandas as pd
import numpy as np
from datetime import date
from typing import Dict, List, Optional

from src.domain.models.country_stability import SovereignPillars, CountryStabilityScore

class SovereignStabilityEngine:
    """
    Model #5: Sovereign Stability & Governance Index (SSGI) Engine.
    
    Evaluates market health based on government honesty, fiscal discipline, 
    social stability, and invasion/conflict risk.
    """

    def __init__(
        self,
        weight_fiscal_fidelity: float = 0.25,
        weight_budget_cap: float = 0.30,
        weight_popular_support: float = 0.25,
        weight_conflict_risk: float = 0.20
    ):
        self.w_fidelity = weight_fiscal_fidelity
        self.w_cap = weight_budget_cap
        self.w_support = weight_popular_support
        self.w_conflict = weight_conflict_risk

    def calculate_budget_cap_score(self, spend_vs_budget_ratio: float) -> float:
        """
        Calculates the Budget Overrun Cap Score based on 200% threshold rule:
        - Ratio <= 1.0 (100%): Full score (100.0)
        - 1.0 < Ratio <= 2.0 (100%-200%): Linear penalty down to 0
        - Ratio > 2.0 (>200%): Severe penalty / 0 score
        """
        if spend_vs_budget_ratio <= 1.0:
            return 100.0
        elif spend_vs_budget_ratio <= 2.0:
            # Linear decay from 100 down to 0 as ratio moves from 1.0 to 2.0
            return float(100.0 * (2.0 - spend_vs_budget_ratio))
        else:
            # Exceeded 200% overrun cap
            return 0.0

    def compute_country_stability(
        self,
        country_code: str,
        country_name: str,
        pillars: SovereignPillars,
        as_of_date: Optional[date] = None
    ) -> CountryStabilityScore:
        if as_of_date is None:
            as_of_date = date.today()

        # 1. Compute Budget Cap Penalty Score
        budget_cap_score = self.calculate_budget_cap_score(pillars.actual_vs_budget_ratio)

        # 2. Calculate Composite SSGI (0 to 100)
        overall_ssgi = (
            self.w_fidelity * pillars.fiscal_fidelity +
            self.w_cap * budget_cap_score +
            self.w_support * pillars.popular_support +
            self.w_conflict * pillars.conflict_invasion_risk
        )
        overall_ssgi = max(0.0, min(100.0, overall_ssgi))

        # 3. Market Health Multiplier [0.0 to 1.0]
        # Uses sigmoid scaling to penalize countries falling below baseline stability (50)
        multiplier = 1.0 / (1.0 + np.exp(-0.1 * (overall_ssgi - 50.0)))
        multiplier = round(float(multiplier), 4)

        return CountryStabilityScore(
            country_code=country_code,
            country_name=country_name,
            as_of_date=as_of_date,
            pillars=pillars,
            budget_cap_score=round(budget_cap_score, 2),
            overall_ssgi_score=round(overall_ssgi, 2),
            market_health_multiplier=multiplier
        )

    def apply_stability_tilting(
        self,
        base_weights: Dict[str, float],
        ticker_country_map: Dict[str, str],
        country_scores: Dict[str, CountryStabilityScore]
    ) -> Dict[str, float]:
        """
        Adjusts portfolio weights based on the country stability score of each asset.
        """
        tilted_weights = {}
        for ticker, weight in base_weights.items():
            country = ticker_country_map.get(ticker, 'US')
            score_obj = country_scores.get(country)
            
            multiplier = score_obj.market_health_multiplier if score_obj else 1.0
            tilted_weights[ticker] = weight * multiplier

        # Renormalize weights to sum to 1.0
        total_w = sum(tilted_weights.values())
        if total_w > 0:
            return {k: round(v / total_w, 6) for k, v in tilted_weights.items()}
        return base_weights
