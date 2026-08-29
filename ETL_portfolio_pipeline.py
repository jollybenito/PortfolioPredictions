import yfinance as yf
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import subprocess
from sqlalchemy import func, text
from database import init_db, get_db_session, StockPrice, engine, DelistedTicker

# ----------------------------
# CONFIG
# ----------------------------
SLEEP_BETWEEN_REQUESTS = 60  # seconds as requested
MAX_RETRIES = 1             # as requested: retry 1 more time
PYTHON_BIN = "python"        # Use python in container

# ----------------------------
# TICKERS (Extracted from DataCollection.ipynb)
# ----------------------------
us_tickers = [
    "AAPL","MSFT","GOOGL","AMZN","META","NVDA","TSLA","BRK-B","JPM","JNJ",
    "V","PG","UNH","HD","MA","XOM","LLY","MRK","AVGO","PEP",
    "COST","ABBV","KO","CVX","BAC","PFE","WMT","TMO","DIS","CSCO",
    "MCD","ACN","ABT","INTC","DHR","LIN","VZ","ADBE","TXN","CMCSA",
    "NEE","CRM","NFLX","PM","QCOM","RTX","HON","IBM","ORCL","UPS",
    "LOW","INTU","AMAT","AMD","GE","CAT","DE","SPGI","ISRG","GS",
    "BLK","AXP","ELV","MDT","TJX","SCHW","NOW","BA","PLD","MO",
    "ADI","CI","SYK","BKNG","GILD","CB","ZTS","LRCX",      "USB",
    "TGT","PNC","SO","ETN","MU","CSX","REGN","APD","EW","HCA"
]

china_tickers = [
    "600519.SS","601398.SS","601288.SS","601857.SS","600036.SS",
    "600276.SS","600030.SS","600887.SS","601988.SS","600028.SS",
    "600000.SS","600309.SS","601166.SS","601668.SS","601318.SS",
    "601088.SS","600050.SS","600104.SS","600048.SS","600016.SS",
    "600019.SS","600031.SS","600547.SS","600585.SS","600690.SS",
    "600703.SS","600809.SS","600837.SS","600893.SS","600918.SS",
    "000001.SZ","000002.SZ","000333.SZ","000651.SZ","000725.SZ",
    "000858.SZ","002415.SZ","002594.SZ","002714.SZ","002352.SZ",
    "002142.SZ","002230.SZ","002475.SZ","002601.SZ","002027.SZ",
    "300015.SZ","300059.SZ","300122.SZ","300124.SZ","300274.SZ",
    "300750.SZ","300760.SZ","300014.SZ","300033.SZ","300142.SZ",
    "300408.SZ","300413.SZ","300433.SZ","300498.SZ","300601.SZ",
    "300628.SZ","300661.SZ","300782.SZ","300832.SZ","300999.SZ"
]

all_tickers = us_tickers + china_tickers + ["SPY"]

def get_latest_date_db(session, ticker):
    try:
        latest_date = session.query(func.max(StockPrice.date)).filter(StockPrice.ticker == ticker).scalar()
        return latest_date
    except Exception as e:
        print(f"Error querying latest date for {ticker}: {e}")
        return None

def is_already_up_to_date(latest_date):
    """
    Heuristic to check if the data is already up to the latest possible trading day.
    """
    if not latest_date: 
        return False
    
    now = datetime.now()
    today = now.date()
    
    # If we already have today's date, we are definitely up to date
    if latest_date >= today:
        return True
        
    # If it's the weekend (Saturday=5, Sunday=6)
    weekday = now.weekday()
    if weekday == 5: # Saturday
        # If we have Friday (yesterday), we are up to date
        if latest_date >= (today - timedelta(days=1)):
            return True
    elif weekday == 6: # Sunday
        if latest_date >= (today - timedelta(days=2)):
            return True
    elif weekday == 0: # Monday
        # Before market open/update on Monday, Friday (3 days ago) is sufficient
        if now.hour < 16: # Assume market data isn't ready until late afternoon
            if latest_date >= (today - timedelta(days=3)):
                return True
            
    # Simple check for 'before market open' - if it's before 7 AM local time, 
    # we might not expect today's data yet and consider yesterday's sufficient
    if now.hour < 7:
        if latest_date >= (today - timedelta(days=1)):
            return True
            
    return False

def download_and_save_db(ticker, start_date):
    session = get_db_session()
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    if start_date:
        fetch_start = (start_date + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        fetch_start = "2015-01-01"
    
    print(f"Downloading {ticker} from {fetch_start} to {end_date}...")
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            # Using Ticker object for better error tracking
            t_obj = yf.Ticker(ticker)
            df = t_obj.history(start=fetch_start, end=end_date, auto_adjust=True)
            
            # Check for delisting signals
            # If historical data is empty and the info object is also empty or missing key data
            if df.empty:
                info = {}
                try: 
                    # info can trigger the 'possibly delisted' print
                    info = t_obj.info 
                except: 
                    pass
                
                # If both are empty, it's likely delisted or ticker changed
                if not info or len(info) < 5:
                    print(f"[CRITICAL] {ticker} appears to be DELISTED. Adding to blacklist.")
                    delisted = DelistedTicker(ticker=ticker, reason="Possibly delisted", date_added=datetime.now().date())
                    session.merge(delisted)
                    session.commit()
                    session.close()
                    return "DELISTED"

            if df.empty:
                print(f"[UNCHANGED] No new data for {ticker}")
                session.close()
                return "UNCHANGED"
            
            # Prepare for DB
            df = df.reset_index()
            # yfinance MultiIndex check 
            # (history() usually returns flattened for single ticker, but safety first)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df.rename(columns={
                'Date': 'date',
                'Close': 'close',
                'High': 'high',
                'Low': 'low',
                'Open': 'open',
                'Volume': 'volume'
            }, inplace=True)
            
            df['ticker'] = ticker
            df['date'] = pd.to_datetime(df['date']).dt.date
            
            # Filter out any data that is already in the DB
            if start_date:
                df = df[df['date'] > start_date]

            if df.empty:
                print(f"[UNCHANGED] No new data for {ticker} (after filtering)")
                session.close()
                return "UNCHANGED"
            
            # Use columns that match our schema
            cols = ['ticker', 'date', 'close', 'high', 'low', 'open', 'volume']
            df = df[cols]
            
            # Save to DB
            df.to_sql('stock_prices', engine, if_exists='append', index=False, method='multi')
            print(f"[OK] Saved {len(df)} rows for {ticker} to DB")
            session.close()
            return True
            
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"[RETRY] {ticker} failed: {e}. Retrying once...")
                time.sleep(5)
            else:
                print(f"[FAILED] {ticker} failed after {MAX_RETRIES} retries: {e}")
                session.close()
                return False
    session.close()
    return False

def main():
    start_time = datetime.now()
    print(f"DB-Based ETL Pipeline started at {start_time}")
    
    init_db()
    session = get_db_session()
    
    # User requested removal of MMC/MCC due to invalidity
    print("Purging invalid ticker data (MMC)...")
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stock_prices WHERE ticker IN ('MMC', 'MCC')"))
        conn.execute(text("DELETE FROM delisted_tickers WHERE ticker IN ('MMC', 'MCC')"))
        conn.commit()
    
    # Fetch delisted tickers to exclude
    delisted_results = session.query(DelistedTicker.ticker).all()
    blacklist = [t[0] for t in delisted_results]
    if blacklist:
        print(f"Skipping {len(blacklist)} delisted tickers: {', '.join(blacklist[:5])}...")

    # 1. Determine start date from DB (using AAPL as benchmark)
    latest_aapl = get_latest_date_db(session, "AAPL")
    
    if not latest_aapl:
        print("No historical data found in DB. Starting from scratch or please run migrate_csv_to_db.py first.")
    else:
        print(f"Latest data point in DB: {latest_aapl}")
    
    failed_stocks = []
    
    # 2. Download and save for all tickers
    for i, ticker in enumerate(all_tickers, 1):
        if ticker in blacklist:
            continue
            
        print(f"\n[{i}/{len(all_tickers)}] {ticker}")
        
        # Get specific latest date for this ticker
        ticker_latest = get_latest_date_db(session, ticker)
        
        # SKIP if already up to date
        if is_already_up_to_date(ticker_latest):
            print(f"[SKIP] {ticker} is already up to date (Latest: {ticker_latest})")
            continue 
             
        result = download_and_save_db(ticker, ticker_latest)
        if result in ["DELISTED", "UNCHANGED"]:
            continue 
            
        if not result:
            failed_stocks.append(ticker)
        
        # Only sleep if we actually saved new data to DB
        if (i < len(all_tickers)) and result is True:
            print(f"Sleeping {SLEEP_BETWEEN_REQUESTS}s...")
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    session.close()

    # Summary of failures
    if failed_stocks:
        print(f"\nWARNING: The following stocks failed to update: {', '.join(failed_stocks)}")
        with open("etl_failures.log", "a") as f:
            f.write(f"{datetime.now()}: Failed stocks: {failed_stocks}\n")
    else:
        print("\nAll stocks updated successfully.")

    # 3. Update Covariance Estimates
    print(f"\n{'='*40}")
    print("Updating Covariance Estimates (from DB)...")
    print(f"{'='*40}")
    try:
        subprocess.run([PYTHON_BIN, "compute_variance.py"], check=True)
        print("Covariance matrices updated.")
    except subprocess.CalledProcessError as e:
        print(f"CRITICAL ERROR: compute_variance.py failed: {e}")

    # 4. Update Portfolios
    print(f"\n{'='*40}")
    print("Updating Portfolios...")
    print(f"{'='*40}")
    try:
        subprocess.run([PYTHON_BIN, "run_all_portfolios.py"], check=True)
        print("Portfolios updated.")
    except subprocess.CalledProcessError as e:
        print(f"CRITICAL ERROR: run_all_portfolios.py failed: {e}")
        return

    # 5. Politician Trades Pipeline
    print(f"\n{'='*40}")
    print("Updating Politician Trades & Signals...")
    print(f"{'='*40}")
    try:
        subprocess.run([PYTHON_BIN, "politician_trades_pipeline.py"], check=True)
        print("Political signals updated.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: politician_trades_pipeline.py failed: {e}")

    # 6. Sentiment Pipeline
    if os.getenv("FINNHUB_API_KEY"):
        print(f"\n{'='*40}")
        print("Updating Market Sentiment Signals (Finnhub)...")
        print(f"{'='*40}")
        try:
            subprocess.run([PYTHON_BIN, "sentiment_pipeline.py"], check=True)
            print("Sentiment results updated.")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: sentiment_pipeline.py failed: {e}")
    else:
        print("\nSkipping Sentiment Pipeline: No FINNHUB_API_KEY found.")

    # 7. Final Comparison
    print(f"\n{'='*40}")
    print("Generating Strategy Comparison Dashboard...")
    print(f"{'='*40}")
    try:
        subprocess.run([PYTHON_BIN, "compare_portfolios.py"], check=True)
        print("Comparison complete.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: compare_portfolios.py failed: {e}")

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\nETL Pipeline completed at {end_time}")
    print(f"Total duration: {duration}")

if __name__ == "__main__":
    main()
