"""Listing-currency assumptions and USD return conversion helpers."""

import pandas as pd

TICKER_CURRENCY_SUFFIXES = {
    ".SS": "CNY", ".SZ": "CNY", ".KS": "KRW", ".HK": "HKD",
    ".SR": "SAR", ".TW": "TWD", ".T": "JPY", ".DE": "EUR",
    ".AS": "EUR", ".PA": "EUR", ".MI": "EUR", ".MC": "EUR",
    ".HE": "EUR", ".L": "GBP", ".SW": "CHF", ".NS": "INR",
    ".BO": "INR", ".TO": "CAD", ".AX": "AUD", ".SI": "SGD",
    ".SA": "BRL", ".MX": "MXN", ".ST": "SEK", ".CO": "DKK",
    ".OL": "NOK", ".TA": "ILS",
}

# Yahoo's XXX=X convention quotes these as local currency per USD. The
# alphabetic base/USD pairs are already USD per unit of local currency.
FX_TICKERS = {
    "EUR": ("EURUSD=X", False),
    "GBP": ("GBPUSD=X", False),
    "AUD": ("AUDUSD=X", False),
    "CNY": ("CNY=X", True),
    "KRW": ("KRW=X", True),
    "HKD": ("HKD=X", True),
    "SAR": ("SAR=X", True),
    "TWD": ("TWD=X", True),
    "JPY": ("JPY=X", True),
    "CHF": ("CHF=X", True),
    "INR": ("INR=X", True),
    "CAD": ("CAD=X", True),
    "SGD": ("SGD=X", True),
    "BRL": ("BRL=X", True),
    "MXN": ("MXN=X", True),
    "SEK": ("SEK=X", True),
    "DKK": ("DKK=X", True),
    "NOK": ("NOK=X", True),
    "ILS": ("ILS=X", True),
}


def currency_for_ticker(ticker: str) -> str:
    for suffix, currency in TICKER_CURRENCY_SUFFIXES.items():
        if ticker.endswith(suffix):
            return currency
    if "." in ticker:
        raise ValueError(f"No listing currency configured for ticker suffix: {ticker}")
    return "USD"


def prices_to_usd_returns(
    local_prices: pd.DataFrame,
    usd_per_local: pd.DataFrame,
    trading_calendar=None,
) -> pd.DataFrame:
    """Convert local-currency closes to USD total-return series on a common calendar."""
    prices = local_prices.copy().sort_index()
    rates = usd_per_local.copy().sort_index()
    prices.index = pd.to_datetime(prices.index).tz_localize(None).normalize()
    if rates.empty:
        rates = pd.DataFrame(index=pd.DatetimeIndex([]))
    else:
        rates.index = pd.to_datetime(rates.index).tz_localize(None).normalize()

    currencies = {ticker: currency_for_ticker(ticker) for ticker in prices.columns}
    required = sorted(set(currencies.values()) - {"USD"})
    missing = sorted(set(required) - set(rates.columns))
    if missing:
        raise ValueError(f"Missing USD FX rates for currencies: {', '.join(missing)}")

    timeline = prices.index.union(rates.index).sort_values()
    prices = prices.reindex(timeline).ffill()
    rates = rates.reindex(timeline).ffill()
    usd_prices = prices.copy()
    for ticker, currency in currencies.items():
        if currency != "USD":
            usd_prices[ticker] = prices[ticker] * rates[currency]

    if trading_calendar is not None:
        calendar = pd.DatetimeIndex(pd.to_datetime(trading_calendar)).tz_localize(None).normalize()
        timeline = usd_prices.index.union(calendar).sort_values()
        usd_prices = usd_prices.reindex(timeline).ffill().reindex(calendar)

    returns = usd_prices.pct_change(fill_method=None)
    return returns.replace([float("inf"), float("-inf")], pd.NA).dropna(how="any")
