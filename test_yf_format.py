import yfinance as yf
import pandas as pd
import os

ticker = "AAPL"
df = yf.download(ticker, start="2024-12-30", end="2025-01-05", auto_adjust=True)
print("Columns:", df.columns)
print("Index name:", df.index.name)
df.to_csv("test_yf.csv")
with open("test_yf.csv", "r") as f:
    print("File content:")
    for _ in range(5):
        print(f.readline(), end="")
