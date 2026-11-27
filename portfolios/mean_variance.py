import pandas as pd
import numpy as np
from pypfopt.efficient_frontier import EfficientFrontier
from pypfopt import expected_returns
import os
import sys
# Add parent directory to path to import database.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import engine
from db_upsert import save_to_db_upsert

DEFAULT_PORTFOLIO_VALUE = 1000.0  # Default total capital USD
MIN_INVESTMENT = 10.0               # Minimum USD per stock (10x broker $1 minimum)

def run_mean_variance(total_portfolio_value: float = DEFAULT_PORTFOLIO_VALUE):
    print(f"Optimization: Mean Variance (Max Sharpe) with Budget ${total_portfolio_value:,.2f}")
    min_weight = MIN_INVESTMENT / total_portfolio_value
    
    # Load returns
    returns = pd.read_csv('returns.csv', index_col=0, parse_dates=True)
    
    # Load Ledoit-Wolf covariance
    # Note: We can also recompute it using pypfopt helpers
    S = pd.read_csv('ledoit_wolf_covariance.csv', index_col=0)
    
    # Estimate expected returns (annualized mean historical returns)
    # Using 252 trading days
    mu = expected_returns.mean_historical_return(returns, returns_data=True, frequency=252)
    
    # --- CLEANING FOR SOLVER ---
    # Drop any NaNs or Infs that would crash the optimizer
    mu = mu.replace([np.inf, -np.inf], np.nan).dropna()
    common_tickers = mu.index.intersection(S.index)
    mu = mu[common_tickers]
    S = S.loc[common_tickers, common_tickers]
    
    print(f"Optimizer stocks after NaN/Inf check: {len(mu)}")
    
    # Max Sharpe Ratio Optimization
    ef = EfficientFrontier(mu, S)
    try:
        weights = ef.max_sharpe()
        cleaned_weights = ef.clean_weights(cutoff=min_weight)
        
        
        # Save weights to CSV (legacy)
        pd.Series(cleaned_weights).to_csv('portfolios/mean_variance_weights.csv')
        
        # Save weights to DB
        last_date = returns.index.max().date()
        weights_df = pd.Series(cleaned_weights).reset_index()
        weights_df.columns = ['ticker', 'weight']
        weights_df['portfolio_type'] = 'mean_variance'
        weights_df['date'] = last_date
        
        try:
            print(f"Saving {len(weights_df)} weights to DB for {last_date}...")
            save_to_db_upsert(weights_df, 'portfolio_weights', engine, ['portfolio_type', 'date'])
            
            # Save Expected Returns to DB
            mu_df = mu.reset_index()
            mu_df.columns = ['ticker', 'value']
            mu_df['date'] = last_date
            save_to_db_upsert(mu_df, 'expected_returns', engine, ['date'])
            print(f"Success: Saved weights and expected returns to DB.")
        except Exception as db_err:
            print(f"DB WRITE ERROR: {db_err}")
        
        # Performance summary
        perf = ef.portfolio_performance(verbose=True)
    except Exception as e:
        print(f"Error during optimization: {e}")

if __name__ == "__main__":
    run_mean_variance()
