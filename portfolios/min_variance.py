import pandas as pd
from pypfopt.efficient_frontier import EfficientFrontier
import os
import sys
# Add parent directory to path to import database.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import engine
from db_upsert import save_to_db_upsert

DEFAULT_PORTFOLIO_VALUE = 1000.0  # Default total capital USD
MIN_INVESTMENT = 10.0               # Minimum USD per stock (10x broker $1 minimum)

def run_min_variance(total_portfolio_value: float = DEFAULT_PORTFOLIO_VALUE):
    print(f"Optimization: Global Minimum Variance with Budget ${total_portfolio_value:,.2f}")
    min_weight = MIN_INVESTMENT / total_portfolio_value
    
    # Load Ledoit-Wolf covariance
    S = pd.read_csv('ledoit_wolf_covariance.csv', index_col=0)
    
    ef = EfficientFrontier(None, S)
    
    try:
        weights = ef.min_volatility()
        cleaned_weights = ef.clean_weights(cutoff=min_weight)
        
        
        # Save weights to CSV (legacy)
        pd.Series(cleaned_weights).to_csv('portfolios/min_variance_weights.csv')
        
        # Save weights to DB
        # We read returns just to get the latest date for the weight record
        returns = pd.read_csv('returns.csv', index_col=0, parse_dates=True)
        last_date = returns.index.max().date()
        
        weights_df = pd.Series(cleaned_weights).reset_index()
        weights_df.columns = ['ticker', 'weight']
        weights_df['portfolio_type'] = 'min_variance'
        weights_df['date'] = last_date
        
        try:
            print(f"Saving {len(weights_df)} Min-Var weights to DB...")
            save_to_db_upsert(weights_df, 'portfolio_weights', engine, ['portfolio_type', 'date'])
            print("Success: Saved Min-Var weights to DB.")
        except Exception as db_err:
            print(f"DB WRITE ERROR: {db_err}")
        
        # Performance summary
        perf = ef.portfolio_performance(verbose=True)
    except Exception as e:
        print(f"Error during optimization: {e}")

if __name__ == "__main__":
    run_min_variance()
