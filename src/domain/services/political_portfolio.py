import pandas as pd
import numpy as np

"""
Political / Congressional Portfolio Strategy (Copy-Portfolio)

This strategy tracks and copies Congressional (Senate & House) trading activity by creating 
a portfolio matching disclosures filed by lawmakers. It functions as a direct portfolio copy 
(non-efficient frontier heuristic).
"""

class PoliticalCopyPortfolio:
    def __init__(self, top_n: int = 15):
        self.top_n = top_n

    def generate_copy_weights(self, signals_df: pd.DataFrame) -> pd.DataFrame:
        """
        Creates a copy portfolio weighted by political net BUY signal values.
        """
        if signals_df.empty:
            return pd.DataFrame(columns=['ticker', 'weight'])

        buys = signals_df[signals_df['signal'] == 'BUY'].copy()
        if buys.empty:
            return pd.DataFrame(columns=['ticker', 'weight'])

        # Sort by signal value and pick top_n
        buys = buys.sort_values(by='net_signal_value', ascending=False).head(self.top_n)
        
        # Normalize weights
        total_val = buys['net_signal_value'].sum()
        buys['weight'] = buys['net_signal_value'] / total_val

        return buys[['ticker', 'weight']]
