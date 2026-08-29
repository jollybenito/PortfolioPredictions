import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

DATA_DIR = "stock_data"
TEST_TICKER = "AAPL"
file_path = os.path.join(DATA_DIR, f"{TEST_TICKER}.csv")
backup_path = file_path + ".bak"

# 1. Backup
import shutil
shutil.copy2(file_path, backup_path)
print(f"Backed up {TEST_TICKER}.csv to {backup_path}")

try:
    # 2. Get latest date
    df_old = pd.read_csv(file_path, skiprows=3, header=None)
    latest_date = pd.to_datetime(df_old[0]).max()
    print(f"Latest date in file: {latest_date.date()}")

    # 3. Download just a few days
    fetch_start = (latest_date + timedelta(days=1)).strftime('%Y-%m-%d')
    fetch_end = (latest_date + timedelta(days=5)).strftime('%Y-%m-%d')
    print(f"Fetching from {fetch_start} to {fetch_end}...")
    
    df_new = yf.download(TEST_TICKER, start=fetch_start, end=fetch_end, auto_adjust=True, progress=False)
    
    if not df_new.empty:
        print(f"Downloaded {len(df_new)} rows.")
        # 4. Append
        df_new.to_csv(file_path, mode='a', header=False)
        print("Appended rows.")
        
        # 5. Verify file structure
        # Check if compute_variance can still read it
        try:
            df_check = pd.read_csv(file_path, skiprows=3, header=None, usecols=[0, 1], names=['Date', 'Close'])
            print(f"File verified. Total rows: {len(df_check)}")
            print(f"New latest date: {df_check['Date'].max()}")
        except Exception as e:
            print(f"Verification FAILED: {e}")
    else:
        print("No new data downloaded (maybe weekend/holiday).")

finally:
    # Restore backup so we don't mess up the actual data before the real run
    shutil.move(backup_path, file_path)
    print("Restored original file.")
