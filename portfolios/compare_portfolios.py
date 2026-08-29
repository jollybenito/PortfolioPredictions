import pandas as pd
import numpy as np
import os

def compare_portfolios():
    # Load data
    returns = pd.read_csv('returns.csv', index_col=0, parse_dates=True)
    S = pd.read_csv('ledoit_wolf_covariance.csv', index_col=0)
    
    portfolio_files = {
        "Mean Variance (Max Sharpe)": "portfolios/mean_variance_weights.csv",
        "Hierarchical Risk Parity (HRP)": "portfolios/hrp_weights.csv",
        "Global Minimum Variance": "portfolios/min_variance_weights.csv"
    }
    
    results = []
    
    # Calculate historical mean returns (annualized)
    mu = returns.mean() * 252
    
    for name, path in portfolio_files.items():
        if not os.path.exists(path):
            print(f"Warning: {path} not found.")
            continue
            
        # Load weights
        weights_df = pd.read_csv(path, index_col=0)
        weights = weights_df.iloc[:, 0]
        
        # Ensure weights are aligned with returns columns
        weights = weights.reindex(returns.columns).fillna(0)
        
        # Portfolio Expected Return
        port_return = np.dot(weights, mu)
        
        # Portfolio Variance
        port_variance = np.dot(weights.T, np.dot(S, weights)) * 252
        
        # Portfolio Volatility
        port_volatility = np.sqrt(port_variance)
        
        # Risk assessment text
        if port_volatility < 0.05:
            risk_level = "Very Low"
        elif port_volatility < 0.15:
            risk_level = "Low"
        elif port_volatility < 0.25:
            risk_level = "Moderate"
        else:
            risk_level = "High"
            
        results.append({
            "Model": name,
            "Exp. Annual Return": f"{port_return:.2%}",
            "Annual Volatility": f"{port_volatility:.2%}",
            "Annual Variance": f"{port_variance:.6f}",
            "Risk Assessment": risk_level
        })
        
    # Create DataFrame and print markdown table
    df_results = pd.DataFrame(results)
    print("\n### Portfolio Model Comparison")
    print(df_results.to_markdown(index=False))
    
    # Save to CSV
    df_results.to_csv('portfolios/comparison_table.csv', index=False)
    print(f"\nSaved comparison to portfolios/comparison_table.csv")

if __name__ == "__main__":
    compare_portfolios()
