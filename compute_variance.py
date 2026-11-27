import pandas as pd
from sklearn.covariance import LedoitWolf
from database import engine
from db_upsert import save_to_db_upsert
from src.adapters.persistence.sql_repository import SQLStockPriceRepository

def compute_variance():
    print("Fetching USD returns from PostgreSQL...")
    returns_df = SQLStockPriceRepository().get_returns_df()

    if returns_df.empty:
        print("ERROR: No complete USD return history found. Run the ETL pipeline and populate FX rates first.")
        return

    last_date = pd.to_datetime(returns_df.index.max()).date()
    print(f"Final data rows: {len(returns_df)} | Final stocks: {returns_df.shape[1]}")

    # The SQL repository returns simple USD returns on the US trading calendar.
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
