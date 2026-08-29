import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys
from database import engine, init_db, MarketSentiment
from db_upsert import save_to_db_upsert
from portfolios.sentiment_portfolio import run_sentiment_portfolio
import subprocess

def simulate_sentiment_data():
    print("--- STEP 1: Simulating Finnhub Data & Custom Formula ---")
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]
    
    # Mock data for AAPL (The Bar)
    aapl_mentions_bar = 500
    
    results = []
    for ticker in tickers:
        # Generate some varying mock metrics
        news_sentiment = np.random.uniform(0.2, 0.8)
        news_buzz = np.random.uniform(0.5, 1.5)
        reddit_mentions = np.random.randint(50, 600)
        reddit_score = np.random.uniform(0.1, 0.6)
        
        # APPLY YOUR FORMULA
        comp_score = (news_sentiment * news_buzz) + (reddit_mentions / aapl_mentions_bar) * reddit_score
        
        print(f"  [SIM] {ticker}: Formula Result = {comp_score:.4f}")
        
        results.append({
            'ticker': ticker,
            'date': datetime.now().date(),
            'news_sentiment': news_sentiment,
            'news_buzz': news_buzz,
            'reddit_mentions': reddit_mentions,
            'reddit_score': reddit_score,
            'composite_score': comp_score
        })
    
    df = pd.DataFrame(results)
    for _, row in df.iterrows():
        save_to_db_upsert(pd.DataFrame([row]), 'market_sentiment', engine, ['ticker', 'date'])
    print(f"Success: {len(results)} mock records saved to DB.\n")

def main():
    init_db()
    
    # 1. Simulate data entry
    simulate_sentiment_data()
    
    # 2. Run the actual portfolio generation logic
    print("--- STEP 2: Running Sentiment Portfolio Generator ---")
    run_sentiment_portfolio()
    print("\n")
    
    # 3. Generate Comparison Dashboard
    print("--- STEP 3: Updating Comparison Dashboard ---")
    try:
        subprocess.run(["python", "compare_portfolios.py"], check=True)
        print("Dashboard updated: portfolio_comparison.png generated.")
    except Exception as e:
        print(f"Dashboard update failed (this is expected if returns.csv is not aligned): {e}")

if __name__ == "__main__":
    main()
