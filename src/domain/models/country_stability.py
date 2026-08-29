from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

@dataclass
class SovereignPillars:
    fiscal_fidelity: float      # 0 to 100: How well spending matches promises
    actual_vs_budget_ratio: float  # Spend / Budget ratio (e.g. 1.15 = 115%, 2.2 = 220%)
    popular_support: float       # 0 to 100: Population approval & political transition stability
    conflict_invasion_risk: float # 0 to 100: 0 = High risk of conflict/invasion, 100 = Low risk / Peaceful

@dataclass
class CountryStabilityScore:
    country_code: str             # e.g., 'US', 'CN', 'UK'
    country_name: str
    as_of_date: date
    pillars: SovereignPillars
    budget_cap_score: float        # Calculated 0 to 100 score based on 200% overrun cap
    overall_ssgi_score: float      # Composite Sovereign Stability & Governance Index (0 to 100)
    market_health_multiplier: float # Multiplier [0.0, 1.0] used for asset allocation tilting
