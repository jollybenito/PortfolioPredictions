import requests
import pandas as pd
from database import engine

API_URL = "https://senatestockwatcher.com/api/0.1/transactions.json"

def check_overlap():
    # 1. Get our tickers
    try:
        our_tickers = pd.read_sql("SELECT DISTINCT ticker FROM stock_prices", engine)['ticker'].tolist()
        print(f"We are tracking {len(our_tickers)} tickers in DB.")
    except:
        print("Could not read stock_prices. Assuming empty.")
        return

    # 2. Get Senate trades
    print("Fetching Senate trades...")
    try:
        response = requests.get(API_URL)
        data = response.json()
        df = pd.DataFrame(data)
        senate_tickers = df['ticker'].unique()
        print(f"Senate API has {len(senate_tickers)} unique tickers.")
        
        # 3. Intersect
        overlap = set(our_tickers) & set(senate_tickers)
        print(f"Overlap: {len(overlap)} tickers.")
        print(f"Sample overlapping tickers: {list(overlap)[:10]}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_overlap()
