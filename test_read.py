import pandas as pd
import os

def test_read():
    files = os.listdir('stock_data')
    sample_file = os.path.join('stock_data', files[0])
    print(f"Testing {sample_file}")
    
    # Try reading with multi-index approach or skipping rows
    try:
        df = pd.read_csv(sample_file, skiprows=3, names=['Date', 'Close', 'High', 'Low', 'Open', 'Volume'])
        print("Heads:")
        print(df.head())
        print("Dtypes:")
        print(df.dtypes)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_read()
