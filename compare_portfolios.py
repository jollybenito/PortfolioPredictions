import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from database import engine

def get_portfolio_metrics(returns_df, weights):
    # Align indices
    common_tickers = list(set(returns_df.columns) & set(weights.index))
    w = weights[common_tickers]
    r = returns_df[common_tickers]
    
    # Normalize weights
    w = w / w.sum()
    
    # Portfolio returns
    port_returns = r.dot(w)
    
    exp_ret = port_returns.mean() * 252
    vol = port_returns.std() * np.sqrt(252)
    sharpe = exp_ret / vol if vol != 0 else 0
    
    return exp_ret, vol, sharpe

def visualize_comparison(results):
    df = pd.DataFrame(results).T
    df.columns = ['Expected Return', 'Volatility', 'Sharpe Ratio']
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    df['Expected Return'].plot(kind='bar', ax=axes[0], color='skyblue', title='Annualized Expected Return')
    df['Volatility'].plot(kind='bar', ax=axes[1], color='salmon', title='Annualized Volatility')
    df['Sharpe Ratio'].plot(kind='bar', ax=axes[2], color='lightgreen', title='Sharpe Ratio')
    
    plt.tight_layout()
    plt.savefig('portfolio_comparison.png')
    print("Comparison plot saved as portfolio_comparison.png")

def main():
    print("Loading data for comparison...")
    # 1. Load returns
    returns = pd.read_csv('returns.csv', index_col=0, parse_dates=True)
    
    strategies = ['mean_variance', 'hrp', 'min_variance', 'masses_sentiment']
    results = {}
    
    # 2. Get weights for existing strategies from DB
    for strat in strategies:
        try:
            w_df = pd.read_sql(f"SELECT ticker, weight FROM portfolio_weights WHERE portfolio_type='{strat}'", engine)
            if not w_df.empty:
                w_series = w_df.set_index('ticker')['weight']
                results[strat.replace('_', ' ').title()] = get_portfolio_metrics(returns, w_series)
            else:
                print(f"Warning: No weights found for {strat}")
        except Exception as e:
            print(f"Error loading {strat}: {e}")
            
    # 3. Create Political Portfolio Weights
    try:
        signals = pd.read_sql("SELECT ticker, net_signal_value FROM stock_signals WHERE signal='BUY'", engine)
        if not signals.empty:
            # Simple weighting by net_signal_value
            p_weights = signals.set_index('ticker')['net_signal_value']
            p_weights = p_weights / p_weights.sum()
            results['Political (Senate)'] = get_portfolio_metrics(returns, p_weights)
        else:
            print("Warning: No BUY signals found for Political Portfolio.")
    except Exception as e:
        print(f"Error creating Political portfolio: {e}")

    if results:
        visualize_comparison(results)
        print("\nSummary Statistics:")
        print(pd.DataFrame(results, index=['Exp Ret', 'Vol', 'Sharpe']).T)
    else:
        print("No results to compare.")

if __name__ == "__main__":
    main()
