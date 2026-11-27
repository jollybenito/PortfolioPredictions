# Local model evaluation

The walk-forward evaluator runs without PostgreSQL. It compares HRP, max-Sharpe mean-variance, global minimum variance, SSGI, and a monthly rebalanced equal-weight equity benchmark using rolling training windows and out-of-sample holding periods. Equity returns are converted to USD and sampled on the US BND trading calendar before fitting or scoring, so daily annualization and rebalancing use one consistent calendar.

## Smoke-test the local setup

```bash
python scripts/evaluate_models.py --demo-synthetic
```

This creates deterministic toy returns in memory. Use it only to confirm the evaluation path runs; its results are not evidence of model performance.

## Download FX rates and the US bond benchmark

```bash
python scripts/download_model_inputs.py \
  --start 2015-10-01 \
  --end 2026-06-07 \
  --output-dir /tmp/portfolio_model_inputs
```

This creates daily `USD_per_<CCY>` FX rates plus adjusted BND and SPY returns outside the repository. BND is used as a broad US investment-grade bond fund proxy; its adjusted prices include reinvested distributions. SPY defines the common US trading calendar used by the PostgreSQL path.

## Evaluate a historical returns file

```bash
python scripts/evaluate_models.py /path/to/returns.csv \
  --returns-kind log \
  --returns-currency local \
  --fx-usd-per-local-csv /tmp/portfolio_model_inputs/fx_usd_per_local.csv \
  --bond-returns-csv /tmp/portfolio_model_inputs/benchmark_returns.csv
```

The older checked-in snapshot contains local-currency log returns, so use `--returns-kind log --returns-currency local` for it. New files from `compute_variance.py` contain simple USD returns; use `--returns-kind simple --returns-currency USD` for those.

The default comparison trains on 756 US trading days, rebalances every 21 US trading days, and charges 10 basis points per unit of turnover. Holdings drift with realized returns between rebalances, and turnover is charged when target weights change. These are starting assumptions; all three can be changed with `--train-days`, `--rebalance-days`, and `--cost-bps`.

The previous checked-in snapshot can be exported to a temporary file while its source revision remains available, without restoring a large file into the project working tree:

```bash
git show <revision-containing-returns.csv>:returns.csv > /tmp/portfolio_returns.csv
python scripts/evaluate_models.py /tmp/portfolio_returns.csv \
  --returns-kind log \
  --returns-currency local \
  --fx-usd-per-local-csv /tmp/portfolio_model_inputs/fx_usd_per_local.csv \
  --bond-returns-csv /tmp/portfolio_model_inputs/benchmark_returns.csv
```

The report includes annualized return and volatility, Sharpe ratio, maximum drawdown, total return, and annualized turnover after estimated costs. It also prints each calendar year's strategy and BND total return; first and last years can be partial. SSGI still uses the example country scores in the application, so treat its results as a software-path comparison until dated country inputs are supplied.

FX conversion uses listing suffixes, e.g. `.T` as JPY and `.L` as GBP. The evaluator and PostgreSQL repository use the same currency map. Unknown suffixes fail instead of silently treating a foreign asset as USD. PostgreSQL returns are sampled on SPY's US trading calendar for consistent 252-day annualization.
