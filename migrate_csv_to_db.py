import os
import pandas as pd
from database import init_db, engine, StockPrice
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATA_DIR = "stock_data"

def migrate():
    print("Initializing database...")
    init_db()
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    total_files = len(csv_files)
    
    print(f"Found {total_files} CSV files to migrate.")
    
    for i, filename in enumerate(csv_files, 1):
        ticker = filename.replace(".csv", "")
        file_path = os.path.join(DATA_DIR, filename)
        
        print(f"[{i}/{total_files}] Migrating {ticker}...")
        
        try:
            # Read CSV skipping the multi-index header (3 rows)
            # Standard order in the CSVs: Date, Close, High, Low, Open, Volume
            df = pd.read_csv(file_path, skiprows=3, header=None, 
                             names=['date', 'close', 'high', 'low', 'open', 'volume'])
            
            df['ticker'] = ticker
            df['date'] = pd.to_datetime(df['date']).dt.date
            
            # Using to_sql for bulk insert
            # 'if_exists'='append' fits our needs since we just initialized the table
            df.to_sql('stock_prices', engine, if_exists='append', index=False, method='multi', chunksize=1000)
            
            print(f"  Successfully migrated {len(df)} rows.")
            
        except Exception as e:
            print(f"  FAILED to migrate {ticker}: {e}")
            
    session.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
