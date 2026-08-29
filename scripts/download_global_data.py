import os
import sys
import numpy as np
import pandas as pd
import yfinance as yf

# Global tickers grouped by Exchange / Country
GLOBAL_TICKERS = {
    # US (NYSE / NASDAQ)
    "AAPL": {"country": "USA", "sector": "Technology", "exchange": "NASDAQ"},
    "MSFT": {"country": "USA", "sector": "Technology", "exchange": "NASDAQ"},
    "AMZN": {"country": "USA", "sector": "Consumer Cyclical", "exchange": "NASDAQ"},
    "GOOGL": {"country": "USA", "sector": "Communication Services", "exchange": "NASDAQ"},
    "NVDA": {"country": "USA", "sector": "Technology", "exchange": "NASDAQ"},
    "JPM": {"country": "USA", "sector": "Financial Services", "exchange": "NYSE"},
    "V": {"country": "USA", "sector": "Financial Services", "exchange": "NYSE"},
    "JNJ": {"country": "USA", "sector": "Healthcare", "exchange": "NYSE"},
    "WMT": {"country": "USA", "sector": "Consumer Defensive", "exchange": "NYSE"},

    # China (Shanghai & Shenzhen)
    "600519.SS": {"country": "China", "sector": "Consumer Defensive", "exchange": "Shanghai Stock Exchange"},
    "600036.SS": {"country": "China", "sector": "Financial Services", "exchange": "Shanghai Stock Exchange"},
    "000858.SZ": {"country": "China", "sector": "Consumer Defensive", "exchange": "Shenzhen Stock Exchange"},
    "000333.SZ": {"country": "China", "sector": "Consumer Cyclical", "exchange": "Shenzhen Stock Exchange"},

    # Japan (Tokyo Stock Exchange .T)
    "7203.T": {"country": "Japan", "sector": "Consumer Cyclical", "exchange": "Tokyo Stock Exchange"}, # Toyota
    "6758.T": {"country": "Japan", "sector": "Technology", "exchange": "Tokyo Stock Exchange"}, # Sony
    "9984.T": {"country": "Japan", "sector": "Communication Services", "exchange": "Tokyo Stock Exchange"}, # SoftBank
    "8306.T": {"country": "Japan", "sector": "Financial Services", "exchange": "Tokyo Stock Exchange"}, # MUFG

    # Hong Kong (.HK)
    "0700.HK": {"country": "Hong Kong", "sector": "Communication Services", "exchange": "Hong Kong Stock Exchange"}, # Tencent
    "9988.HK": {"country": "Hong Kong", "sector": "Consumer Cyclical", "exchange": "Hong Kong Stock Exchange"}, # Alibaba
    "1299.HK": {"country": "Hong Kong", "sector": "Financial Services", "exchange": "Hong Kong Stock Exchange"}, # AIA Group

    # UK (London Stock Exchange .L)
    "SHEL.L": {"country": "United Kingdom", "sector": "Energy", "exchange": "London Stock Exchange"}, # Shell
    "AZN.L": {"country": "United Kingdom", "sector": "Healthcare", "exchange": "London Stock Exchange"}, # AstraZeneca
    "HSBA.L": {"country": "United Kingdom", "sector": "Financial Services", "exchange": "London Stock Exchange"}, # HSBC

    # France (Euronext Paris .PA)
    "MC.PA": {"country": "France", "sector": "Consumer Cyclical", "exchange": "Euronext Paris"}, # LVMH
    "OR.PA": {"country": "France", "sector": "Consumer Defensive", "exchange": "Euronext Paris"}, # L'Oreal
    "TTE.PA": {"country": "France", "sector": "Energy", "exchange": "Euronext Paris"}, # TotalEnergies

    # Germany (XETRA .DE)
    "SAP.DE": {"country": "Germany", "sector": "Technology", "exchange": "Deutsche Börse"},
    "SIE.DE": {"country": "Germany", "sector": "Industrials", "exchange": "Deutsche Börse"}, # Siemens
    "ALV.DE": {"country": "Germany", "sector": "Financial Services", "exchange": "Deutsche Börse"}, # Allianz

    # Switzerland (SIX Swiss .SW)
    "NESN.SW": {"country": "Switzerland", "sector": "Consumer Defensive", "exchange": "SIX Swiss Exchange"}, # Nestle
    "NOVN.SW": {"country": "Switzerland", "sector": "Healthcare", "exchange": "SIX Swiss Exchange"}, # Novartis
    "ROG.SW": {"country": "Switzerland", "sector": "Healthcare", "exchange": "SIX Swiss Exchange"}, # Roche

    # India (NSE .NS)
    "RELIANCE.NS": {"country": "India", "sector": "Energy", "exchange": "National Stock Exchange of India"},
    "TCS.NS": {"country": "India", "sector": "Technology", "exchange": "National Stock Exchange of India"},
    "HDFCBANK.NS": {"country": "India", "sector": "Financial Services", "exchange": "National Stock Exchange of India"},

    # Canada (Toronto .TO)
    "RY.TO": {"country": "Canada", "sector": "Financial Services", "exchange": "Toronto Stock Exchange"}, # Royal Bank of Canada
    "TD.TO": {"country": "Canada", "sector": "Financial Services", "exchange": "Toronto Stock Exchange"}, # Toronto-Dominion
    "SHOP.TO": {"country": "Canada", "sector": "Technology", "exchange": "Toronto Stock Exchange"}, # Shopify

    # Taiwan (.TW)
    "2330.TW": {"country": "Taiwan", "sector": "Technology", "exchange": "Taiwan Stock Exchange"}, # TSMC
    "2317.TW": {"country": "Taiwan", "sector": "Technology", "exchange": "Taiwan Stock Exchange"}, # Foxconn

    # South Korea (KRX .KS)
    "005930.KS": {"country": "South Korea", "sector": "Technology", "exchange": "Korea Exchange"}, # Samsung Electronics
    "000660.KS": {"country": "South Korea", "sector": "Technology", "exchange": "Korea Exchange"}, # SK Hynix

    # Australia (ASX .AX)
    "BHP.AX": {"country": "Australia", "sector": "Basic Materials", "exchange": "Australian Securities Exchange"},
    "CBA.AX": {"country": "Australia", "sector": "Financial Services", "exchange": "Australian Securities Exchange"},

    # Netherlands (.AS)
    "ASML.AS": {"country": "Netherlands", "sector": "Technology", "exchange": "Euronext Amsterdam"},
    "UNA.AS": {"country": "Netherlands", "sector": "Consumer Defensive", "exchange": "Euronext Amsterdam"}, # Unilever

    # Saudi Arabia (.SR)
    "2222.SR": {"country": "Saudi Arabia", "sector": "Energy", "exchange": "Saudi Exchange (Tadawul)"}, # Saudi Aramco

    # Brazil (.SA)
    "PETR4.SA": {"country": "Brazil", "sector": "Energy", "exchange": "B3"}, # Petrobras
    "VALE3.SA": {"country": "Brazil", "sector": "Basic Materials", "exchange": "B3"}, # Vale

    # Sweden (.ST)
    "VOLV-B.ST": {"country": "Sweden", "sector": "Industrials", "exchange": "Nasdaq Stockholm"},
    "ERIC-B.ST": {"country": "Sweden", "sector": "Technology", "exchange": "Nasdaq Stockholm"},

    # Denmark (.CO)
    "NOVO-B.CO": {"country": "Denmark", "sector": "Healthcare", "exchange": "Nasdaq Copenhagen"}, # Novo Nordisk

    # Spain (.MC)
    "SAN.MC": {"country": "Spain", "sector": "Financial Services", "exchange": "Bolsa de Madrid"}, # Santander
    "ITX.MC": {"country": "Spain", "sector": "Consumer Cyclical", "exchange": "Bolsa de Madrid"}, # Inditex

    # Italy (.MI)
    "RACE.MI": {"country": "Italy", "sector": "Consumer Cyclical", "exchange": "Borsa Italiana"}, # Ferrari
    "ENEL.MI": {"country": "Italy", "sector": "Utilities", "exchange": "Borsa Italiana"},

    # Singapore (.SI)
    "D05.SI": {"country": "Singapore", "sector": "Financial Services", "exchange": "Singapore Exchange"}, # DBS Group

    # Mexico (.MX)
    "WALMEX.MX": {"country": "Mexico", "sector": "Consumer Defensive", "exchange": "Mexican Stock Exchange"},

    # Norway (.OL)
    "EQNR.OL": {"country": "Norway", "sector": "Energy", "exchange": "Oslo Børs"}, # Equinor

    # Finland (.HE)
    "NOKIA.HE": {"country": "Finland", "sector": "Technology", "exchange": "Nasdaq Helsinki"},

    # Israel (.TA)
    "TEVA.TA": {"country": "Israel", "sector": "Healthcare", "exchange": "Tel Aviv Stock Exchange"},
}

def main():
    print(f"Fetching data for {len(GLOBAL_TICKERS)} global assets across top 30 exchanges...")
    tickers_list = list(GLOBAL_TICKERS.keys())
    
    start_date = "2015-11-01"
    end_date = "2026-06-06"
    
    # Download adj close
    df_raw = yf.download(tickers_list, start=start_date, end=end_date, progress=True, auto_adjust=False)
    if "Adj Close" in df_raw:
        data = df_raw["Adj Close"]
    elif "Close" in df_raw:
        data = df_raw["Close"]
    else:
        data = df_raw

    if isinstance(data, pd.Series):
        data = data.to_frame()

    # Drop columns with > 50% missing values
    valid_data = data.dropna(thresh=int(len(data) * 0.5), axis=1)
    # Forward fill then backward fill remaining small gaps
    valid_data = valid_data.ffill().bfill()

    # Calculate log returns
    log_returns = np.log(valid_data / valid_data.shift(1)).dropna()
    log_returns.index = log_returns.index.strftime('%Y-%m-%d')
    log_returns.index.name = "date"

    # Save to returns.csv
    log_returns.to_csv("returns.csv")
    print(f"Successfully updated returns.csv! New dimensions: {log_returns.shape}")

if __name__ == "__main__":
    main()
