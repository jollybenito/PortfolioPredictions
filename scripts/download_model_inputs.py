"""Download FX rates and a broad US bond ETF return series for local evaluation."""
import argparse
from pathlib import Path
import sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.domain.models.currency import FX_TICKERS


def adjusted_close(symbol: str, start: str, end: str) -> pd.Series:
    history = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False, threads=False)
    if history.empty:
        raise RuntimeError(f"No history returned for {symbol}.")
    close = history["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna().astype(float)
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    close.name = symbol
    return close


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2015-10-01")
    parser.add_argument("--end", default="2026-06-07", help="Exclusive end date, as in yfinance download.")
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/portfolio_model_inputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    fx_rates = {}
    for currency, (symbol, invert) in FX_TICKERS.items():
        series = adjusted_close(symbol, args.start, args.end)
        if invert:
            series = 1 / series
        fx_rates[f"USD_per_{currency}"] = series

    fx_frame = pd.concat(fx_rates, axis=1).sort_index()
    fx_path = args.output_dir / "fx_usd_per_local.csv"
    fx_frame.to_csv(fx_path, index_label="date")

    bnd_close = adjusted_close("BND", args.start, args.end)
    bnd_returns = bnd_close.pct_change().dropna().rename("BND")
    spy_close = adjusted_close("SPY", args.start, args.end)
    spy_returns = spy_close.pct_change().dropna().rename("SPY")
    benchmark_returns = pd.concat([bnd_returns, spy_returns], axis=1).sort_index()
    benchmark_path = args.output_dir / "benchmark_returns.csv"
    benchmark_returns.to_csv(benchmark_path, index_label="date")

    print(f"FX rates: {fx_path} ({fx_frame.index.min().date()} to {fx_frame.index.max().date()})")
    print(f"BND total-return proxy: {benchmark_path} ({bnd_returns.index.min().date()} to {bnd_returns.index.max().date()})")
    print(f"SPY trading calendar: {spy_returns.index.min().date()} to {spy_returns.index.max().date()}")
    print("FX columns are USD per one unit of the named local currency.")


if __name__ == "__main__":
    main()
