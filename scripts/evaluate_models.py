"""Run a PostgreSQL-free walk-forward comparison of the portfolio selectors."""
import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.application.portfolio_calculation_use_case import PortfolioCalculationUseCase
from src.domain.models.currency import currency_for_ticker, prices_to_usd_returns


@dataclass
class InMemoryReturnsRepository:
    returns: pd.DataFrame

    def get_returns_df(self) -> pd.DataFrame:
        return self.returns


def load_returns(
    path: str,
    returns_kind: str,
    returns_currency: str,
    fx_rates_path: str = None,
    trading_calendar: pd.Index = None,
) -> tuple[pd.DataFrame, Dict[str, int]]:
    returns = pd.read_csv(path, index_col=0, parse_dates=True)
    returns = returns.apply(pd.to_numeric, errors="coerce")
    returns = returns.replace([np.inf, -np.inf], np.nan)
    returns = returns.dropna(axis=1, how="any").sort_index()
    if returns_kind == "log":
        returns = np.expm1(returns)
    returns = returns.loc[:, returns.std() > 1e-12]
    if returns.empty or returns.shape[1] < 2:
        raise ValueError("The input needs at least two assets with complete numeric returns.")
    if returns.index.has_duplicates:
        raise ValueError("The input contains duplicate dates.")

    foreign_tickers = {}
    fx_rates = pd.DataFrame()
    if returns_currency == "local":
        foreign_tickers = {
            ticker: currency_for_ticker(ticker)
            for ticker in returns.columns
            if currency_for_ticker(ticker) != "USD"
        }
    if foreign_tickers and not fx_rates_path:
        currencies = sorted(set(foreign_tickers.values()))
        raise ValueError(f"Foreign listings need FX conversion to USD. Supply --fx-usd-per-local-csv for: {', '.join(currencies)}.")
    if foreign_tickers:
        fx_rates = pd.read_csv(fx_rates_path, index_col=0, parse_dates=True).sort_index()
        fx_rates.columns = [column.removeprefix("USD_per_") for column in fx_rates.columns]
        for ticker, currency in foreign_tickers.items():
            column = currency
            if column not in fx_rates:
                raise ValueError(f"FX file is missing USD_per_{column}, required by {ticker}.")

    if trading_calendar is not None:
        calendar = pd.DatetimeIndex(trading_calendar).tz_localize(None).normalize()
        calendar = calendar[(calendar >= returns.index.min()) & (calendar <= returns.index.max())]
        if calendar.empty:
            raise ValueError("No overlap between equity returns and benchmark trading dates.")
        local_price_indices = (1 + returns).cumprod()
        if returns_currency == "local":
            returns = prices_to_usd_returns(local_price_indices, fx_rates, trading_calendar=calendar)
        else:
            expanded_index = local_price_indices.index.union(calendar).sort_values()
            local_price_indices = local_price_indices.reindex(expanded_index).ffill().reindex(calendar)
            returns = local_price_indices.pct_change(fill_method=None).fillna(0.0)
        returns.index.name = "date"

    counts = pd.Series(foreign_tickers).value_counts().sort_index().to_dict()
    return returns, counts


def make_demo_returns(rows: int = 1_500, seed: int = 17) -> pd.DataFrame:
    """Create a repeatable toy dataset for checking the local evaluation path."""
    tickers = ["AAPL", "MSFT", "JPM", "JNJ", "600519.SS", "000001.SZ"]
    rng = np.random.default_rng(seed)
    market = rng.normal(0.00025, 0.009, size=rows)
    regional = rng.normal(0.00005, 0.006, size=(rows, 2))
    noise = rng.normal(0, 0.008, size=(rows, len(tickers)))
    returns = np.column_stack([
        market * 0.9 + regional[:, 0] * 0.1 + noise[:, 0],
        market * 1.1 + regional[:, 0] * 0.1 + noise[:, 1],
        market * 0.8 + regional[:, 0] * 0.1 + noise[:, 2],
        market * 0.6 + regional[:, 0] * 0.1 + noise[:, 3],
        market * 0.5 + regional[:, 1] * 0.5 + noise[:, 4],
        market * 0.7 + regional[:, 1] * 0.3 + noise[:, 5],
    ])
    return pd.DataFrame(
        returns,
        columns=tickers,
        index=pd.bdate_range("2018-01-01", periods=rows, name="date"),
    )


def calculate_weights(strategy: str, training_returns: pd.DataFrame) -> pd.Series:
    use_case = PortfolioCalculationUseCase(InMemoryReturnsRepository(training_returns))
    result = use_case.calculate_custom_portfolio(
        strategy=strategy,
        budget=1_000.0,
        risk_level=15.0,
    )
    weights = pd.Series(result["allocations_pct"], dtype=float).reindex(training_returns.columns).fillna(0.0)
    total = float(weights.sum())
    if total <= 0:
        raise ValueError(f"{strategy} produced no active allocations.")
    return weights / total


def summarize(daily_returns: pd.Series, turnover: float) -> Dict[str, float]:
    wealth = (1 + daily_returns).cumprod()
    annual_return = float(wealth.iloc[-1] ** (252 / len(daily_returns)) - 1)
    annual_volatility = float(daily_returns.std(ddof=1) * np.sqrt(252))
    sharpe = float(daily_returns.mean() / daily_returns.std(ddof=1) * np.sqrt(252)) if daily_returns.std(ddof=1) else 0.0
    drawdown = wealth / wealth.cummax() - 1
    return {
        "annual_return_pct": annual_return * 100,
        "annual_volatility_pct": annual_volatility * 100,
        "sharpe": sharpe,
        "max_drawdown_pct": float(drawdown.min()) * 100,
        "total_return_pct": float(wealth.iloc[-1] - 1) * 100,
        "annual_turnover": turnover * 252 / len(daily_returns),
    }


def walk_forward(returns: pd.DataFrame, train_days: int, rebalance_days: int, cost_bps: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    strategies = ("hrp", "mean_variance", "min_variance", "sovereign_stability", "equal_weight")
    output = {}
    out_of_sample_returns = {}
    cost_rate = cost_bps / 10_000

    for strategy in strategies:
        net_returns = []
        turnover_total = 0.0
        current_holdings = None
        for test_start in range(train_days, len(returns), rebalance_days):
            test_end = min(test_start + rebalance_days, len(returns))
            training = returns.iloc[test_start - train_days:test_start]
            test = returns.iloc[test_start:test_end]
            training = training.loc[:, training.std() > 1e-12]
            if training.shape[1] < 2:
                raise ValueError(f"Only {training.shape[1]} non-constant assets in training window ending at row {test_start}.")
            if strategy == "equal_weight":
                weights = pd.Series(1 / training.shape[1], index=training.columns, dtype=float)
            else:
                weights = calculate_weights(strategy, training)

            if current_holdings is None:
                turnover = float(weights.abs().sum())
            else:
                all_tickers = current_holdings.index.union(weights.index)
                turnover = float((weights.reindex(all_tickers, fill_value=0) - current_holdings.reindex(all_tickers, fill_value=0)).abs().sum() / 2)
            turnover_total += turnover
            test_period = test.reindex(columns=weights.index)
            daily_values = []
            drifted_weights = weights.copy()
            for position, (date, asset_returns) in enumerate(test_period.iterrows()):
                gross_return = float(asset_returns.dot(drifted_weights))
                net_return = gross_return - turnover * cost_rate if position == 0 else gross_return
                daily_values.append(net_return)
                drifted_weights = drifted_weights.mul(1 + asset_returns).div(1 + gross_return)
            if daily_values:
                net_returns.append(pd.Series(daily_values, index=test_period.index))
            current_holdings = drifted_weights

        if not net_returns:
            raise ValueError("No out-of-sample returns were produced; lower --train-days.")
        strategy_returns = pd.concat(net_returns).sort_index()
        output[strategy] = summarize(strategy_returns, turnover_total)
        out_of_sample_returns[strategy] = strategy_returns

    report = pd.DataFrame(output).T.rename_axis("strategy").reset_index()
    return report, pd.DataFrame(out_of_sample_returns)


def load_benchmarks(path: str) -> tuple[pd.Series, pd.DatetimeIndex]:
    benchmarks = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    missing = {"BND", "SPY"} - set(benchmarks.columns)
    if missing:
        raise ValueError(f"Benchmark file is missing required columns: {', '.join(sorted(missing))}.")
    bond_returns = pd.to_numeric(benchmarks["BND"], errors="coerce").dropna()
    spy_calendar = pd.DatetimeIndex(benchmarks.index[benchmarks["SPY"].notna()])
    return bond_returns, spy_calendar


def annual_returns_table(out_of_sample_returns: pd.DataFrame, bond_returns: pd.Series) -> pd.DataFrame:
    first_date, last_date = out_of_sample_returns.index.min(), out_of_sample_returns.index.max()
    portfolio_annual = (1 + out_of_sample_returns).groupby(out_of_sample_returns.index.year).prod() - 1
    bond_period = bond_returns.loc[first_date:last_date]
    bond_annual = (1 + bond_period).groupby(bond_period.index.year).prod() - 1
    annual = portfolio_annual.join(bond_annual.rename("BND"), how="left")
    annual.index.name = "year"
    annual = annual.mul(100).reset_index()
    annual["trading_days"] = out_of_sample_returns.groupby(out_of_sample_returns.index.year).size().to_numpy()
    first_year = int(out_of_sample_returns.index.min().year)
    last_year = int(out_of_sample_returns.index.max().year)
    annual["coverage"] = ["partial" if year in (first_year, last_year) else "full" for year in annual["year"]]
    return annual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("returns_csv", nargs="?", help="Path to local daily returns CSV (date index, ticker columns).")
    parser.add_argument("--demo-synthetic", action="store_true", help="Use a deterministic toy series; smoke test only, not performance evidence.")
    parser.add_argument("--returns-kind", choices=("log", "simple"), default="log",
                        help="Legacy global returns.csv uses log returns; SQL export uses simple returns.")
    parser.add_argument("--returns-currency", choices=("local", "USD"), default="local",
                        help="Use local when FX conversion is required; use USD for converted returns files.")
    parser.add_argument("--fx-usd-per-local-csv", help="Daily USD-per-local-currency FX rates, one USD_per_<CCY> column per foreign currency.")
    parser.add_argument("--bond-returns-csv", help="Daily simple total returns for the BND US bond benchmark.")
    parser.add_argument("--train-days", type=int, default=756, help="Rolling training window in trading days.")
    parser.add_argument("--rebalance-days", type=int, default=21, help="Out-of-sample holding period in trading days.")
    parser.add_argument("--cost-bps", type=float, default=10.0, help="Trading cost charged per unit of turnover in basis points.")
    args = parser.parse_args()

    if args.demo_synthetic:
        if args.returns_csv or args.fx_usd_per_local_csv or args.bond_returns_csv:
            parser.error("Pass either CSV inputs or --demo-synthetic, not both.")
        returns = make_demo_returns()
        source_label = "deterministic synthetic demo (not investment evidence)"
        foreign_counts = {}
        dates = returns.index
        rng = np.random.default_rng(91)
        bond_returns = pd.Series(rng.normal(0.00008, 0.002, len(dates)), index=dates, name="BND")
        trading_calendar = dates
    elif args.returns_csv:
        if not args.bond_returns_csv:
            parser.error("Historical comparisons require --bond-returns-csv for the US bond benchmark.")
        bond_returns, trading_calendar = load_benchmarks(args.bond_returns_csv)
        returns, foreign_counts = load_returns(
            args.returns_csv,
            args.returns_kind,
            args.returns_currency,
            args.fx_usd_per_local_csv,
            trading_calendar=trading_calendar,
        )
        source_label = args.returns_csv
    else:
        parser.error("Provide a returns CSV or pass --demo-synthetic.")

    if args.train_days < 2 or len(returns) <= args.train_days:
        raise SystemExit(f"Need more than {args.train_days} complete daily observations; found {len(returns)}.")

    report, oos_returns = walk_forward(returns, args.train_days, args.rebalance_days, args.cost_bps)
    bond_returns = bond_returns.loc[oos_returns.index.min():oos_returns.index.max()]
    if bond_returns.empty or bond_returns.index.min() > oos_returns.index.min() or bond_returns.index.max() < oos_returns.index.max():
        raise ValueError("BND benchmark does not cover the out-of-sample date range.")
    bond_summary = summarize(bond_returns, 0.0)
    report = pd.concat([
        report,
        pd.DataFrame([{"strategy": "BND", **bond_summary}]),
    ], ignore_index=True)
    annual = annual_returns_table(oos_returns, bond_returns)
    print(f"Source: {source_label}")
    print(f"Data: {returns.index.min().date()} to {returns.index.max().date()}, {len(returns)} days, {returns.shape[1]} assets")
    if args.demo_synthetic:
        print("Demo includes synthetic FX-free assets and a synthetic BND series (smoke test only).")
    elif args.returns_currency == "USD":
        print("Input returns are declared USD-denominated; no FX conversion applied by this evaluator.")
    elif foreign_counts:
        print("Converted local returns to USD using FX rates:")
        print("  " + ", ".join(f"{currency}: {count} assets" for currency, count in foreign_counts.items()))
    print(f"Walk-forward: {args.train_days}-day training, {args.rebalance_days}-day rebalance, {args.cost_bps:g} bps cost")
    print(report.to_string(index=False, formatters={column: "{:.2f}".format for column in report.select_dtypes(include="number").columns}))
    print("\nCalendar-year return (%) on common out-of-sample dates; first/last years may be partial:")
    annual_formatters = {
        column: "{:.2f}".format
        for column in annual.select_dtypes(include="number").columns
        if column not in {"year", "trading_days"}
    }
    print(annual.to_string(index=False, formatters=annual_formatters))


if __name__ == "__main__":
    main()
