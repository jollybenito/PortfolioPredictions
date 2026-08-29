import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import text
from database import engine, init_db, SenatorTrade, SenatorScore, StockSignal
from db_upsert import save_to_db_upsert
import os
import time

# ----------------------------
# CONFIG
# ----------------------------
DATA_SOURCE_URL = "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json"
LOOKBACK_YEARS = 2
SIGNAL_DECAY_DAYS = 30
PURGE_ON_RUN = True

# Helper to map amount strings to midpoints
AMOUNT_MAP = {
    "$1,001 - $15,000": 8000,
    "$15,001 - $50,000": 32500,
    "$50,001 - $100,000": 75000,
    "$100,001 - $250,000": 175000,
    "$250,001 - $500,000": 375000,
    "$500,001 - $1,000,000": 750000,
    "$1,000,001 - $5,000,000": 3000000,
    "$5,000,001 - $25,000,000": 15000000,
    "$25,000,001 - $50,000,000": 37500000,
    "Over $50,000,000": 50000000,
    "Unknown": 1000
}

def fetch_and_purge():
    print("Fetching Senate trades from Github mirror...")
    
    # Retry logic for network issues
    for attempt in range(3):
        try:
            response = requests.get(DATA_SOURCE_URL, timeout=30)
            response.raise_for_status()
            data = response.json()
            break
        except Exception as e:
            if attempt < 2:
                print(f"  Network attempt {attempt+1} failed ({e}). Retrying in 5s...")
                time.sleep(5)
            else:
                print(f"  CRITICAL: Could not reach Senate data source after 3 attempts.")
                raise e
    
    df = pd.DataFrame(data)
    
    # Filter for stocks with tickers
    df = df[df['ticker'].notna() & (df['ticker'] != '--')]
    df['ticker'] = df['ticker'].str.upper().str.strip()
    
    # Map amounts
    df['amount_midpoint'] = df['amount'].map(lambda x: AMOUNT_MAP.get(x, 1000))
    df['date'] = pd.to_datetime(df['transaction_date']).dt.date
    
    init_db()
    if PURGE_ON_RUN:
        print("Purging old trade data...")
        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE senator_trades RESTART IDENTITY"))
            conn.commit()
            
    # Save to DB
    to_save = df[['senator', 'ticker', 'date', 'type', 'amount_midpoint']]
    to_save.to_sql('senator_trades', engine, if_exists='append', index=False)
    print(f"Imported {len(to_save)} trades.")
    return df

def score_senators():
    print("Scoring politicians...")
    # 1. Load prices to calculate returns
    prices_df = pd.read_sql("SELECT ticker, date, close FROM stock_prices", engine)
    prices_df['date'] = pd.to_datetime(prices_df['date']).dt.date
    prices_df = prices_df.pivot(index='date', columns='ticker', values='close')
    
    # 2. Load trades
    trades = pd.read_sql("SELECT * FROM senator_trades WHERE type IN ('Purchase', 'Sale Full', 'Sale Partial')", engine)
    trades['date'] = pd.to_datetime(trades['date']).dt.date
    
    scores = []
    senators = trades['senator'].unique()
    
    for senator in senators:
        s_trades = trades[(trades['senator'] == senator) & (trades['type'] == 'Purchase')]
        if len(s_trades) < 3: continue # Need minimum activity to score
        
        returns = []
        for _, trade in s_trades.iterrows():
            t = trade['ticker']
            d = trade['date']
            if t in prices_df.columns:
                p_at_trade = prices_df.loc[prices_df.index >= d, t].head(1)
                p_60d = prices_df.loc[prices_df.index >= d + timedelta(days=60), t].head(1)
                if not p_at_trade.empty and not p_60d.empty:
                    ret = (p_60d.values[0] / p_at_trade.values[0]) - 1
                    returns.append(ret)
        
        if not returns: continue
        
        hist_ret = np.mean(returns)
        const_fact = 1 / (1 + np.std(returns)) # High std = low consistency
        act_fact = np.log1p(len(s_trades))
        
        final_score = hist_ret * const_fact * act_fact
        
        scores.append({
            'senator': senator,
            'historical_return': hist_ret,
            'consistency_factor': const_fact,
            'activity_factor': act_fact,
            'final_score': final_score,
            'last_updated': datetime.now().date()
        })
        
    score_df = pd.DataFrame(scores)
    score_df.to_sql('senator_scores', engine, if_exists='replace', index=False)
    print(f"Scored {len(score_df)} senators.")
    return score_df

def generate_signals():
    print("Generating stock signals...")
    # Load scores and recent trades
    scores = pd.read_sql("SELECT senator, final_score FROM senator_scores", engine).set_index('senator')
    cutoff = datetime.now().date() - timedelta(days=365) # 1 year lookback
    trades = pd.read_sql(f"SELECT * FROM senator_trades WHERE date >= '{cutoff}'", engine)
    trades['date'] = pd.to_datetime(trades['date']).dt.date
    
    # Filter trades to only those in our universe
    our_tickers = pd.read_sql("SELECT DISTINCT ticker FROM stock_prices", engine)['ticker'].tolist()
    our_tickers = [t.upper() for t in our_tickers]
    
    trades = trades[trades['ticker'].isin(our_tickers)]
    
    if trades.empty:
        print(f"  No trades found for our {len(our_tickers)} tracked stocks in the last year (Cutoff: {cutoff}).")
        return pd.DataFrame()
    
    print(f"  INTERSECTION FOUND: Analyzing {len(trades)} trades across {len(trades['ticker'].unique())} tracked stocks...")
    
    tickers = trades['ticker'].unique()
    signals = []
    today = datetime.now().date()
    
    for ticker in tickers:
        t_trades = trades[trades['ticker'] == ticker]
        net_signal = 0
        w_buys = 0
        w_sells = 0
        
        for _, tr in t_trades.iterrows():
            score = scores.loc[tr['senator'], 'final_score'] if tr['senator'] in scores.index else 0.01
            days_ago = (today - tr['date']).days
            recency = np.exp(-days_ago / SIGNAL_DECAY_DAYS)
            
            strength = score * tr['amount_midpoint'] * recency
            
            if 'Purchase' in tr['type']:
                net_signal += strength
                w_buys += strength
            elif 'Sale' in tr['type']:
                net_signal -= strength
                w_sells += strength
        
        # Risk score = sells - buys (Higher = more exiting politicians)
        risk = w_sells - w_buys
        sig_label = 'HOLD'
        
        # Lowered thresholds significantly to ensure we get a portfolio
        if net_signal > 0.1: sig_label = 'BUY'
        elif net_signal < -0.1: sig_label = 'EXIT'
        
        if sig_label != 'HOLD':
            print(f"  [SIGNAL] {ticker}: {sig_label} (Net Strength: {net_signal:.4f})")
        
        signals.append({
            'ticker': ticker,
            'signal': sig_label,
            'net_signal_value': net_signal,
            'risk_score': risk,
            'date': today
        })
        
    signal_df = pd.DataFrame(signals)
    if not signal_df.empty:
        save_to_db_upsert(signal_df, 'stock_signals', engine, ['ticker', 'date'])
        print(f"Generated and synced signals for {len(signal_df)} tickers.")
    else:
        print("No signals generated.")
    return signal_df

def main():
    fetch_and_purge()
    score_senators()
    generate_signals()

if __name__ == "__main__":
    main()
