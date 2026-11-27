from datetime import datetime, timedelta
from typing import List
import yfinance as yf
import pandas as pd

from src.domain.models.stock_price import FXRate, StockPrice
from src.domain.models.currency import FX_TICKERS
from src.ports.repositories import MarketDataProvider

class YFinanceAdapter(MarketDataProvider):
    def fetch_historical_prices(self, ticker: str, start_date: str, end_date: str) -> List[StockPrice]:
        t_obj = yf.Ticker(ticker)
        df = t_obj.history(start=start_date, end=end_date, auto_adjust=True)
        
        if df.empty:
            return []

        df = df.reset_index()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        prices = []
        for idx, row in df.iterrows():
            prices.append(
                StockPrice(
                    ticker=ticker,
                    date=pd.to_datetime(row['Date']).date(),
                    close=float(row['Close']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    open=float(row['Open']),
                    volume=int(row['Volume'])
                )
            )
        return prices

    def fetch_historical_fx_rates(self, currency: str, start_date: str, end_date: str) -> List[FXRate]:
        if currency not in FX_TICKERS:
            raise ValueError(f"No Yahoo Finance FX ticker configured for {currency}.")
        symbol, invert = FX_TICKERS[currency]
        history = yf.Ticker(symbol).history(start=start_date, end=end_date, auto_adjust=True)
        if history.empty:
            return []
        close = history["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        if invert:
            close = 1 / close
        rates = []
        for timestamp, value in close.dropna().items():
            if float(value) <= 0:
                continue
            rates.append(FXRate(
                currency=currency,
                date=pd.Timestamp(timestamp).date(),
                usd_per_unit=float(value),
            ))
        return rates

    def check_delisted(self, ticker: str) -> bool:
        t_obj = yf.Ticker(ticker)
        try:
            info = t_obj.info
            if not info or len(info) < 5:
                return True
        except Exception:
            return True
        return False

    def fetch_pe_ratios(self, tickers: List[str]) -> dict:
        """
        Fetches trailing P/E ratios for a list of tickers via yfinance.
        Missing or non-existent P/E values are returned as None (treated as extreme cases).
        """
        pe_ratios = {}
        for ticker in tickers:
            try:
                t_obj = yf.Ticker(ticker)
                info = t_obj.info
                # Prefer trailingPE, fallback to forwardPE
                pe = info.get('trailingPE') or info.get('forwardPE')
                if pe is not None and isinstance(pe, (int, float)) and pe > 0:
                    pe_ratios[ticker] = float(pe)
                else:
                    pe_ratios[ticker] = None
            except Exception:
                pe_ratios[ticker] = None
        return pe_ratios
