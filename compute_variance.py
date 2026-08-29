import pandas as pd
import numpy as np
import os
from sklearn.covariance import LedoitWolf
from database import engine, get_db_session, StockPrice, CovarianceMatrix
from db_upsert import save_to_db_upsert

def compute_variance():
    print("Fetching data from database...")
    
    # Query all prices focusing on ticker, date, and close
    query = "SELECT ticker, date, close FROM stock_prices ORDER BY date ASC"
    df = pd.read_sql(query, engine)
    
    if df.empty:
        print("ERROR: No data found in database. Run the ETL pipeline or migration first.")
        return

    # Convert date to datetime
    df['date'] = pd.to_datetime(df['date'])
    last_date = df['date'].max().date()
    
    # Pivot the data to get dates as index and tickers as columns
    print("Pivoting data...")
    price_df = df.pivot(index='date', columns='ticker', values='close')
    price_df.sort_index(inplace=True)
    
    # Handle missing values
    price_df.ffill(inplace=True)
    
    # Cleaning
    price_df.dropna(axis=1, thresh=int(len(price_df) * 0.9), inplace=True)
    price_df.dropna(inplace=True)
    
    print(f"Final data rows: {len(price_df)} | Final stocks: {price_df.shape[1]}")
    
    # Calculate Log Returns
    returns_df = np.log(price_df / price_df.shift(1)).dropna()
    returns_df.to_csv('returns.csv')
    
    # helper to save matrix to DB
    def save_matrix_to_db(cov_df, method_name, date_val):
        print(f"Saving {method_name} covariance to DB...")
        melted = cov_df.reset_index().melt(id_vars=cov_df.index.name or 'index', var_name='ticker_b', value_name='value')
        melted.rename(columns={(cov_df.index.name or 'index'): 'ticker_a'}, inplace=True)
        melted['method'] = method_name
        melted['date'] = date_val
        save_to_db_upsert(melted, 'covariance_estimates', engine, ['method', 'date'])

    # 1. Standard Covariance Matrix
    sample_cov = returns_df.cov()
    sample_cov.to_csv('sample_covariance.csv')
    save_matrix_to_db(sample_cov, 'sample', last_date)
    
    # 2. Ledoit-Wolf Shrinkage Covariance Matrix
    lw = LedoitWolf()
    lw.fit(returns_df)
    lw_cov = pd.DataFrame(lw.covariance_, index=returns_df.columns, columns=returns_df.columns)
    lw_cov.index.name = 'ticker'
    lw_cov.to_csv('ledoit_wolf_covariance.csv')
    save_matrix_to_db(lw_cov, 'ledoit_wolf', last_date)
    
    print(f"\nComputation complete for date {last_date}.")

if __name__ == "__main__":
    compute_variance()
