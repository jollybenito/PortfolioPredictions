import finnhub
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import time
from database import engine, init_db, MarketSentiment, get_db_session
from db_upsert import save_to_db_upsert
from dotenv import load_dotenv

load_dotenv()

# ----------------------------
# CONFIG
# ----------------------------
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")
if not FINNHUB_KEY:
    print("WARNING: FINNHUB_API_KEY not found in .env. Sentiment pipeline will not run.")

# Tickers to track (subset for testing or full list)
from ETL_portfolio_pipeline import us_tickers, china_tickers
all_tickers = list(set(us_tickers + china_tickers + ["AAPL"])) # Ensure AAPL is included as the benchmark

def get_sentiment_data(client, ticker):
    """
    Fetches both News and Social sentiment from Finnhub.
    """
    try:
        # 1. News Sentiment
        news = client.news_sentiment(ticker)
        news_score = news.get('sentiment', {}).get('sentimentScore', 0)
        news_buzz = news.get('buzz', {}).get('buzz', 0)
        
        # 2. Social Sentiment (Reddit)
        # We look at the last week to get a stable mention count/score
        social = client.social_sentiment(ticker)
        reddit_data = social.get('reddit', [])
        
        if reddit_data:
            # Average the score and sum the mentions for the last week
            reddit_mentions = sum(day.get('mention', 0) for day in reddit_data)
            reddit_score = np.mean([day.get('score', 0) for day in reddit_data])
        else:
            reddit_mentions = 0
            reddit_score = 0
            
        return {
            'ticker': ticker,
            'news_sentiment': news_score,
            'news_buzz': news_buzz,
            'reddit_mentions': reddit_mentions,
            'reddit_score': reddit_score
        }
    except Exception as e:
        print(f"  Error fetching Finnhub data for {ticker}: {e}")
        return None

def main():
    if not FINNHUB_KEY:
        return
        
    print(f"Starting Sentiment Pipeline at {datetime.now()}")
    client = finnhub.Client(api_key=FINNHUB_KEY)
    init_db()
    
    results = []
    
    # 1. Get AAPL data first as the "Bar"
    print("Fetching benchmark ticker (AAPL)...")
    aapl_data = get_sentiment_data(client, "AAPL")
    if not aapl_data or aapl_data['reddit_mentions'] == 0:
        print("  Could not fetch AAPL benchmark or AAPL has 0 mentions. Using fallback denominator (1).")
        aapl_mentions_bar = 1
    else:
        aapl_mentions_bar = aapl_data['reddit_mentions']
        print(f"  AAPL Benchmark Mentions: {aapl_mentions_bar}")

    # 2. Fetch for all other tickers
    for i, ticker in enumerate(all_tickers):
        print(f"[{i+1}/{len(all_tickers)}] Fetching sentiment for {ticker}...")
        data = get_sentiment_data(client, ticker)
        if data:
            # APPLY FORMULA: 
            # sentimentScore * buzz + (Reddit Mentions / AAPL_Reddit_Mentions) * Reddit score
            comp_score = (data['news_sentiment'] * data['news_buzz']) + \
                         (data['reddit_mentions'] / aapl_mentions_bar) * data['reddit_score']
            
            data['composite_score'] = comp_score
            data['date'] = datetime.now().date()
            results.append(data)
            
        # Finnhub free tier rate limit is 60 calls/min. 
        # Each ticker takes 2 calls (news + social). 
        # So we can do ~30 tickers per minute.
        time.sleep(1.2) 

    if results:
        df = pd.DataFrame(results)
        # Use a custom upsert: for sentiment, we usually want one row per ticker per date
        for _, row in df.iterrows():
            single_row_df = pd.DataFrame([row])
            save_to_db_upsert(single_row_df, 'market_sentiment', engine, ['ticker', 'date'])
        print(f"Saved {len(results)} sentiment records to DB.")

if __name__ == "__main__":
    main()
