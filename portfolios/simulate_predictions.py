import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

def simulate_predictions(days=90, simulations=1000):
    print(f"Simulating {days} days for each portfolio model...")
    
    # Load data
    returns = pd.read_csv('returns.csv', index_col=0, parse_dates=True)
    S = pd.read_csv('ledoit_wolf_covariance.csv', index_col=0)
    mu_historical = returns.mean() # Daily mean returns
    
    portfolio_files = {
        "Mean Variance": "portfolios/mean_variance_weights.csv",
        "HRP": "portfolios/hrp_weights.csv",
        "Min Variance": "portfolios/min_variance_weights.csv"
    }
    
    plt.figure(figsize=(12, 7))
    
    colors = {'Mean Variance': 'blue', 'HRP': 'green', 'Min Variance': 'red'}
    
    for name, path in portfolio_files.items():
        if not os.path.exists(path):
            continue
            
        # Load weights
        weights_df = pd.read_csv(path, index_col=0)
        weights = weights_df.iloc[:, 0].reindex(returns.columns).fillna(0).values
        
        # Portfolio stats (daily)
        port_mu = np.dot(weights, mu_historical)
        port_sigma = np.sqrt(np.dot(weights.T, np.dot(S, weights)))
        
        # Monte Carlo Simulation
        # Price process: P_t = P_0 * exp(sum(r_i))
        # Initial value = 1.0 (0% return)
        
        # Random daily returns for all simulations
        # shape: (days, simulations)
        daily_sim_returns = np.random.normal(port_mu, port_sigma, (days, simulations))
        
        # Cumulative returns
        # shape: (days + 1, simulations)
        cum_returns = np.exp(np.cumsum(daily_sim_returns, axis=0)) - 1
        cum_returns = np.vstack([np.zeros(simulations), cum_returns]) # Start at 0
        
        # Stats
        mean_path = np.mean(cum_returns, axis=1)
        median_path = np.median(cum_returns, axis=1)
        lower_bound = np.percentile(cum_returns, 5, axis=1)
        upper_bound = np.percentile(cum_returns, 95, axis=1)
        
        # Time axis
        t = np.arange(days + 1)
        
        # Plot
        plt.plot(t, mean_path, label=f'{name} (Mean)', color=colors[name], linewidth=2)
        plt.fill_between(t, lower_bound, upper_bound, color=colors[name], alpha=0.1)
        
        print(f"Finished {name}: Expected 90-day return: {mean_path[-1]:.2%}")

    plt.title(f"90-Day Portfolio Return Projections (Monte Carlo Simulation)")
    plt.xlabel("Days")
    plt.ylabel("Cumulative Return")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.axhline(0, color='black', linestyle='--', linewidth=1)
    
    # Save chart
    output_path = 'portfolios/return_predictions.png'
    plt.savefig(output_path, dpi=300)
    print(f"Chart saved to {output_path}")

if __name__ == "__main__":
    simulate_predictions()
