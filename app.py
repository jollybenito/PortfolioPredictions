import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
import json
import calendar
import html
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

# Ensure src modules can be resolved
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.application.portfolio_calculation_use_case import PortfolioCalculationUseCase
from src.domain.services.hrp_optimizer import RiskTargetedHRP
from src.domain.models.stock_metadata import get_metadata, TICKER_METADATA_REGISTRY
from ibkr_executor import (
    check_ibkr_configured,
    check_ibkr_connection,
    execute_rebalance,
    get_current_positions,
    get_account_info,
    get_accounts
)

# ---------------------------------------------------------
# Streamlit Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Portfolio Predictions · Model Workspace",
    page_icon="P",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root { --app-bg:#0b1110; --app-surface:#111a18; --app-raised:#17221f; --app-line:#263530; --app-ink:#edf4ef; --app-muted:#9aaba2; --app-accent:#a9df83; --app-accent-ink:#14200f; }
html, body, [class*="css"] { font-family:"DM Sans",sans-serif; }
.stApp { background:var(--app-bg); color:var(--app-ink); }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stToolbar"] { right:1rem; }
.block-container { max-width:1480px; padding:1.7rem 3.25rem 4rem; }
[data-testid="stSidebar"] { background:#101816; border-right:1px solid var(--app-line); }
[data-testid="stSidebar"] > div:first-child { padding-top:1.4rem; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 { font-size:1.08rem; letter-spacing:-.02em; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color:#c8d4cd; font-size:.85rem; }
[data-testid="stSidebar"] hr { border-color:var(--app-line); margin:1.15rem 0; }
h1,h2,h3 { color:var(--app-ink); letter-spacing:-.045em; }
h1 { font-size:clamp(2.25rem,4vw,3.5rem)!important; line-height:1.03!important; font-weight:600!important; }
h2 { font-size:1.48rem!important; font-weight:600!important; }
h3 { font-size:1.08rem!important; font-weight:600!important; }
p,li { color:#c6d2cb; }
.brand-row { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.2rem 0 1.9rem; border-bottom:1px solid var(--app-line); margin-bottom:2.15rem; }
.brand-lockup { display:flex; align-items:center; gap:.75rem; }
.brand-mark { width:2.2rem; height:2.2rem; display:grid; place-items:center; border-radius:.7rem; background:var(--app-accent); color:var(--app-accent-ink); font-weight:700; letter-spacing:-.08em; }
.brand-name { color:var(--app-ink); font-size:.96rem; font-weight:600; letter-spacing:-.02em; }
.brand-product { color:var(--app-muted); font:500 .68rem "IBM Plex Mono",monospace; letter-spacing:.1em; text-transform:uppercase; margin-top:.12rem; }
.brand-context { color:var(--app-muted); font:500 .72rem "IBM Plex Mono",monospace; letter-spacing:.08em; text-transform:uppercase; }
.page-intro { max-width:850px; margin-bottom:1.45rem; }
.page-kicker { color:var(--app-accent); font:500 .72rem "IBM Plex Mono",monospace; letter-spacing:.11em; text-transform:uppercase; margin:0 0 .8rem; }
.page-intro h1 { margin:0 0 .72rem; }
.page-intro p { max-width:52rem; color:var(--app-muted); font-size:1rem; margin:0; }
.data-status { display:flex; align-items:center; flex-wrap:wrap; gap:.65rem; color:var(--app-muted); font-size:.78rem; margin:1.5rem 0 2rem; }
.status-dot { width:.48rem; height:.48rem; border-radius:50%; background:#e0ae63; box-shadow:0 0 0 4px #e0ae631b; }
.data-status strong { color:#dbe8df; font-weight:500; }
.status-divider { width:1px; height:1rem; background:var(--app-line); margin:0 .2rem; }
.horizon-panel { display:grid; grid-template-columns:minmax(220px,.85fr) minmax(280px,1.15fr); gap:1.5rem; align-items:center; border:1px solid var(--app-line); background:linear-gradient(115deg,#121d19,#101816 72%); border-radius:16px; padding:1.25rem 1.4rem; margin:.85rem 0 2rem; }
.horizon-heading { padding:.25rem 0 .7rem; margin-top:.8rem; }
.block-container div[data-testid="stHorizontalBlock"]:has(.stRadio) { border:1px solid var(--app-line); border-radius:16px; background:linear-gradient(115deg,#121d19,#101816 72%); padding:1.15rem 1.35rem; margin-bottom:1.8rem; }
.horizon-title { color:var(--app-ink); font-size:1.02rem; font-weight:600; margin:0 0 .25rem; }
.horizon-copy { color:var(--app-muted); font-size:.82rem; line-height:1.45; margin:0; }
.refresh-meta { display:flex; flex-wrap:wrap; gap:.45rem 1.35rem; justify-content:flex-end; }
.refresh-item { display:flex; flex-direction:column; gap:.2rem; }
.refresh-label { color:var(--app-muted); font:500 .65rem "IBM Plex Mono",monospace; letter-spacing:.08em; text-transform:uppercase; }
.refresh-value { color:#e1ebe4; font-size:.82rem; }
.refresh-value em { color:var(--app-accent); font-style:normal; }
.stRadio > div[role="radiogroup"] { display:inline-flex; gap:.28rem; padding:.28rem; border:1px solid var(--app-line); border-radius:10px; background:#0b1210; }
.stRadio > div[role="radiogroup"] label { min-height:2.55rem; border-radius:7px; padding:.45rem .9rem; margin:0; transition:background .16s ease,color .16s ease; }
.stRadio > div[role="radiogroup"] label:has(input:checked) { background:var(--app-accent); color:var(--app-accent-ink); }
.stRadio > div[role="radiogroup"] label:has(input:checked) p { color:var(--app-accent-ink); font-weight:600; }
.stRadio > div[role="radiogroup"] label p { font-size:.86rem; color:#c5d1ca; }
[data-testid="stMetric"] { background:var(--app-surface); border:1px solid var(--app-line); border-radius:12px; padding:1rem 1.1rem; }
[data-testid="stMetricLabel"] p { color:var(--app-muted); font-size:.78rem; }
[data-testid="stMetricValue"] { color:var(--app-ink); font-size:1.6rem; }
[data-testid="stDataFrame"] { border:1px solid var(--app-line); border-radius:12px; overflow:hidden; }
[data-testid="stExpander"] { background:var(--app-surface); border:1px solid var(--app-line); border-radius:12px; margin-bottom:.55rem; }
[data-testid="stExpander"] summary { color:var(--app-ink); }
[data-testid="stPlotlyChart"] { border:1px solid var(--app-line); border-radius:12px; background:var(--app-surface); padding:.25rem; }
.recommendation-card { background:linear-gradient(110deg,#1a2a22,#121b18 68%); border:1px solid #3b5946; border-radius:16px; padding:1.4rem 1.6rem; margin:1.6rem 0 2rem; }
.recommendation-label { color:var(--app-accent); font:500 .68rem "IBM Plex Mono",monospace; text-transform:uppercase; letter-spacing:.1em; margin-bottom:.6rem; }
.recommendation-name { color:var(--app-ink); font-size:1.35rem; font-weight:600; letter-spacing:-.03em; margin-bottom:1.2rem; }
.recommendation-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1rem; }
.recommendation-metric { border-top:1px solid #34463b; padding-top:.7rem; }
.recommendation-metric span { display:block; color:var(--app-muted); font-size:.72rem; margin-bottom:.25rem; }
.recommendation-metric strong { color:var(--app-ink); font-size:1.08rem; font-weight:600; }
.stButton > button { border-radius:9px; border:1px solid var(--app-line); transition:transform .14s ease,background .14s ease,border-color .14s ease; }
.stButton > button:hover { transform:translateY(-1px); border-color:#789879; }
.stButton > button[kind="primary"] { background:var(--app-accent); color:var(--app-accent-ink); border-color:var(--app-accent); }
[data-testid="stNotification"] { border-radius:12px; }
code,.mono { font-family:"IBM Plex Mono",monospace; }
@media(max-width:900px) { .block-container { padding:1.35rem 1.4rem 3rem; } .horizon-panel { grid-template-columns:1fr; gap:1rem; } .refresh-meta { justify-content:flex-start; } }
@media(max-width:560px) { .block-container { padding:.95rem 1rem 2rem; } .brand-context { display:none; } .brand-row { margin-bottom:1.5rem; } .recommendation-grid { grid-template-columns:1fr; gap:.7rem; } .recommendation-metric { display:flex; justify-content:space-between; align-items:center; } .recommendation-metric strong { font-size:.95rem; } }
</style>
""", unsafe_allow_html=True)

MAX_ALLOWED_RISK_PCT = 40.0  # 40% risk ceiling rule
MARKET_TIMEZONE = ZoneInfo("America/New_York")
MODEL_REFRESH_TIME = time(16, 30)


class StaticReturnsRepository:
    """Give a model run one fixed, schedule-bounded market history."""

    def __init__(self, returns: pd.DataFrame):
        self.returns = returns

    def get_returns_df(self) -> pd.DataFrame:
        return self.returns.copy()

st.markdown("""
<div class="brand-row">
  <div class="brand-lockup">
    <div class="brand-mark">P</div>
    <div><div class="brand-name">Portfolio Predictions</div><div class="brand-product">Model workspace</div></div>
  </div>
  <div class="brand-context">Research · Allocation · Risk</div>
</div>
<div class="page-intro">
  <div class="page-kicker">Portfolio research</div>
  <h1>Compare allocation models</h1>
  <p>Review expected return, volatility and holdings across long and medium investment horizons.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Load Data & Dependencies
# ---------------------------------------------------------
def get_use_case():
    """Auto-detect environment: use CSV repo on Streamlit Cloud, SQL locally."""
    try:
        from src.adapters.persistence.sql_repository import SQLStockPriceRepository
        repo = SQLStockPriceRepository()
        returns = repo.get_returns_df()
        if not returns.empty:
            return PortfolioCalculationUseCase(StaticReturnsRepository(returns)), "sql", returns
    except Exception:
        pass

    from src.adapters.persistence.csv_repository import CSVStockPriceRepository
    repo = CSVStockPriceRepository(csv_path="returns.csv")
    returns = repo.get_returns_df()
    return PortfolioCalculationUseCase(StaticReturnsRepository(returns)), "csv", returns


def _last_weekday_of_month(year: int, month: int) -> date:
    day = calendar.monthrange(year, month)[1]
    while date(year, month, day).weekday() >= 5:
        day -= 1
    return date(year, month, day)


def _refresh_is_complete(refresh_date: date, now: datetime) -> bool:
    return refresh_date < now.date() or (
        refresh_date == now.date()
        and (now.hour, now.minute) >= (MODEL_REFRESH_TIME.hour, MODEL_REFRESH_TIME.minute)
    )


def get_model_refresh_dates(horizon: str, now: datetime = None) -> tuple[date, date]:
    """Return the latest completed and next scheduled horizon refresh dates."""
    now = now or datetime.now(MARKET_TIMEZONE)
    candidates = []
    if horizon == "Medium":
        for offset in range(-1, 15):
            year, month = now.year, now.month - offset
            while month <= 0:
                year -= 1
                month += 12
            candidates.append(_last_weekday_of_month(year, month))
    else:
        candidates = [_last_weekday_of_month(year, 12) for year in range(now.year + 1, now.year - 5, -1)]

    completed = next(day for day in candidates if _refresh_is_complete(day, now))
    upcoming = next(day for day in sorted(candidates) if day > now.date() or not _refresh_is_complete(day, now))
    return completed, upcoming


def load_political_signals(repo_type: str, as_of: date) -> pd.DataFrame:
    """Load the latest persisted Congressional trade signals available by a cutoff."""
    if repo_type != "sql":
        return pd.DataFrame()

    from database import StockSignal, get_db_session

    session = get_db_session()
    try:
        latest_date = (
            session.query(StockSignal.date)
            .filter(StockSignal.date <= as_of)
            .order_by(StockSignal.date.desc())
            .first()
        )
        if latest_date is None:
            return pd.DataFrame()
        rows = (
            session.query(StockSignal.ticker, StockSignal.signal, StockSignal.net_signal_value)
            .filter(StockSignal.date == latest_date[0])
            .all()
        )
        return pd.DataFrame(rows, columns=["ticker", "signal", "net_signal_value"])
    except Exception:
        return pd.DataFrame()
    finally:
        session.close()

def get_last_etl_timestamp(repo_type: str) -> str:
    if repo_type == "sql":
        try:
            from database import get_db_session, ETLMetadata
            session = get_db_session()
            try:
                record = session.query(ETLMetadata).filter(ETLMetadata.key == "last_full_etl_run").first()
                if record and record.value:
                    dt = datetime.fromisoformat(record.value)
                    return dt.strftime("%B %d, %Y at %I:%M %p UTC")
            finally:
                session.close()
        except Exception:
            pass
        return "Unknown"
    else:
        try:
            if os.path.exists("etl_metadata.json"):
                with open("etl_metadata.json", "r") as f:
                    data = json.load(f)
                    ts = data.get("last_full_etl_run")
                    if ts:
                        dt = datetime.fromisoformat(ts)
                        return dt.strftime("%B %d, %Y at %I:%M %p UTC")
        except Exception:
            pass
        return "Unknown"

_, repo_type, returns_df = get_use_case()
returns_df.index = pd.to_datetime(returns_df.index)
last_etl = get_last_etl_timestamp(repo_type)

if returns_df.empty:
    st.error("No historical return data available. Please ensure returns.csv or database connection is initialized.")
    st.stop()

st.markdown(
    f'<div class="data-status"><span class="status-dot"></span>'
    f'<span>Historical market data</span><span class="status-divider"></span>'
    f'<strong>Last full update: {html.escape(last_etl)}</strong>'
    '<span class="status-divider"></span><span>For research purposes</span></div>',
    unsafe_allow_html=True,
)

all_available_tickers = sorted(returns_df.columns.tolist())

# ---------------------------------------------------------
# Investment Horizon Selector
# ---------------------------------------------------------
st.markdown(
    '<div class="horizon-heading"><div><div class="horizon-title">Choose an investment horizon</div>'
    '<p class="horizon-copy">Compare models using data aligned to their review schedule.</p></div></div>',
    unsafe_allow_html=True,
)
horizon_col, schedule_col = st.columns([1, 1.35], vertical_alignment="center")
with horizon_col:
    selected_horizon = st.radio(
        "Choose a model timeframe:",
        options=["Long", "Medium"],
        horizontal=True,
        label_visibility="collapsed",
    )
last_refresh_date, next_refresh_date = get_model_refresh_dates(selected_horizon)
refresh_cutoff = pd.Timestamp(last_refresh_date)
model_returns = returns_df.loc[returns_df.index <= refresh_cutoff]
model_data_date = model_returns.index.max().date() if not model_returns.empty else None
if selected_horizon == "Medium":
    refresh_copy = "Monthly · after the last weekday"
else:
    refresh_copy = "Annual · after the last weekday of Q4"
with schedule_col:
    data_date_label = model_data_date.strftime("%b %d, %Y") if model_data_date else "No data available"
    st.markdown(
        '<div class="refresh-meta">'
        f'<div class="refresh-item"><span class="refresh-label">Review cycle</span><span class="refresh-value"><em>{refresh_copy}</em></span></div>'
        f'<div class="refresh-item"><span class="refresh-label">Prices through</span><span class="refresh-value">{data_date_label}</span></div>'
        f'<div class="refresh-item"><span class="refresh-label">Next update</span><span class="refresh-value">{next_refresh_date:%b %d, %Y} · after U.S. close</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

# Extract available metadata groups dynamically
available_countries = sorted(list(set(get_metadata(t).country for t in all_available_tickers)))
available_sectors = sorted(list(set(get_metadata(t).sector for t in all_available_tickers if get_metadata(t).sector != "Unknown")))
available_exchanges = sorted(list(set(get_metadata(t).exchange for t in all_available_tickers)))

# ---------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------
st.sidebar.header("Portfolio settings")

# 1. Budget Input ($200 to $999,999,999)
st.sidebar.subheader("Investment budget · USD")
budget = st.sidebar.number_input(
    "Total Capital to Invest:",
    min_value=200.0,
    max_value=999_999_999.0,
    value=10_000.0,
    step=100.0,
    format="%.2f",
    help="Enter investment amount between $200 and $999,999,999 USD"
)

# 2. Risk-Adjusted Metric Selection
st.sidebar.subheader("Evaluation metric")
metric_descriptions = {
    "Sharpe Ratio — Return relative to total volatility": "sharpe",
    "Sortino Ratio — Return relative to downside risk only": "sortino",
    "Treynor Ratio — Return relative to systematic market risk (beta)": "treynor"
}
selected_metric_label = st.sidebar.radio(
    "Select ratio for model evaluation:",
    options=list(metric_descriptions.keys()),
    index=0,
    help="Choose the risk-adjusted metric used to evaluate portfolio performance quality."
)
selected_metric = metric_descriptions[selected_metric_label]

# 3. Group Exclusion Menu (Country, Sector, Exchange)
st.sidebar.markdown("---")
st.sidebar.subheader("Market filters")
st.sidebar.markdown("*Filter out categories of assets by market metadata:*")

excluded_countries = st.sidebar.multiselect(
    "Exclude Markets by Country:",
    options=available_countries,
    default=[],
    help="Select countries to exclude all stocks domiciled there."
)

excluded_sectors = st.sidebar.multiselect(
    "Exclude Sectors:",
    options=available_sectors,
    default=[],
    help="Select sectors to mass-exclude."
)

excluded_exchanges = st.sidebar.multiselect(
    "Exclude Stock Exchanges:",
    options=available_exchanges,
    default=[],
    help="Select specific exchanges to exclude."
)

st.sidebar.markdown("---")
st.sidebar.subheader("Valuation filter")
max_pe_input = st.sidebar.number_input(
    "Maximum Allowed P/E Ratio:",
    min_value=0.0,
    max_value=500.0,
    value=0.0,
    step=5.0,
    help="Set maximum Price-to-Earnings ratio. Set to 0 to disable filter."
)
max_pe_ratio = max_pe_input if max_pe_input > 0 else None

# 4. Individual Stock Exclusion Menu
st.sidebar.markdown("---")
st.sidebar.subheader("Asset exclusions")
excluded_tickers = st.sidebar.multiselect(
    "Exclude specific assets:",
    options=all_available_tickers,
    default=[],
    help="Select individual tickers to exclude from recalculation."
)

# ---------------------------------------------------------
# IBKR Gateway Connection Status (Sidebar)
# ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("Broker connection · IBKR")
ibkr_configured = check_ibkr_configured()
ibkr_connected = False

if ibkr_configured:
    connected, msg = check_ibkr_connection()
    ibkr_connected = connected
    if connected:
        st.sidebar.success(f"✅ {msg}")
    else:
        st.sidebar.warning(f"⚠️ {msg}")
        st.sidebar.caption("Ensure IBKR Client Portal Gateway is running on `http://localhost:5000`")
else:
    st.sidebar.info("💡 Set `IBKR_GATEWAY_URL` in `.env` (default: http://localhost:5000)")

# ---------------------------------------------------------
# Run ALL Models & Enforce Risk Ceiling (< 40%)
# ---------------------------------------------------------
ALL_STRATEGIES = {
    "mean_variance": {
        "name": "Mean-Variance (Max Sharpe)",
        "icon": "📐",
        "description": "Markowitz efficient frontier optimization focused on maximizing return per unit of volatility.",
        "horizons": ("Long", "Medium")
    },
    "hrp": {
        "name": "Hierarchical Risk Parity (HRP)",
        "icon": "🌳",
        "description": "Clusters assets hierarchically to achieve robust, well-diversified profit allocation.",
        "horizons": ("Long", "Medium")
    },
    "sovereign_stability": {
        "name": "Sovereign Stability Index (SSGI)",
        "icon": "🌐",
        "description": "Tilts asset allocation based on country-level fiscal and geopolitical stability metrics.",
        "horizons": ("Long", "Medium")
    },
    "political": {
        "name": "Capitol Trades Signals",
        "icon": "🏛️",
        "description": "Signal-driven portfolio mirroring aggregated legislative trading activity.",
        "horizons": ("Medium",)
    },
    "min_variance": {
        "name": "Global Minimum Variance",
        "icon": "🛡️",
        "description": "Constructs the lowest-volatility portfolio to preserve capital.",
        "horizons": ("Long", "Medium")
    }
}


def classify_risk(volatility_pct: float) -> tuple:
    """Classify portfolio risk based on annualized volatility."""
    if volatility_pct > MAX_ALLOWED_RISK_PCT:
        return f"🚫 Discarded (> {MAX_ALLOWED_RISK_PCT:.0f}% Risk Limit)", "discarded"
    elif volatility_pct < 10:
        return "🟢 Low Risk", "low"
    elif volatility_pct < 18:
        return "🟡 Moderate Risk", "moderate"
    elif volatility_pct < 28:
        return "🟠 High Risk", "high"
    else:
        return "🔴 Very High Risk", "very_high"


def run_all_models(
    model_use_case, strategies, budget, excluded_tickers, excluded_countries,
    excluded_sectors, excluded_exchanges, max_pe_ratio, metric, political_signals_df
):
    """Run every strategy and return results dict."""
    results = {}
    for strategy_key in strategies.keys():
        try:
            default_risk_target = 20.0

            result = model_use_case.calculate_custom_portfolio(
                strategy=strategy_key,
                budget=budget,
                risk_level=default_risk_target,
                excluded_tickers=excluded_tickers,
                excluded_countries=excluded_countries,
                excluded_sectors=excluded_sectors,
                excluded_exchanges=excluded_exchanges,
                max_pe_ratio=max_pe_ratio,
                metric=metric,
                political_signals_df=political_signals_df if strategy_key == "political" else None,
            )
            
            vol = result["metrics"]["volatility_pct"]
            if vol > MAX_ALLOWED_RISK_PCT:
                result["is_discarded"] = True
                result["discard_reason"] = f"Annualized risk ({vol:.2f}%) exceeds maximum allowed threshold of {MAX_ALLOWED_RISK_PCT:.0f}%"
            else:
                result["is_discarded"] = False

            results[strategy_key] = result
        except Exception as e:
            results[strategy_key] = {"error": str(e)}
    return results


# Execute all models live based on inputs
visible_strategies = {
    key: info for key, info in ALL_STRATEGIES.items()
    if selected_horizon in info["horizons"]
}
model_use_case = PortfolioCalculationUseCase(StaticReturnsRepository(model_returns))
political_signals_df = load_political_signals(repo_type, last_refresh_date)
model_results = run_all_models(
    model_use_case, visible_strategies, budget, excluded_tickers, excluded_countries,
    excluded_sectors, excluded_exchanges, max_pe_ratio, selected_metric, political_signals_df
)

# ---------------------------------------------------------
# Determine Top Recommended Model (Highest Profit with <40% Risk)
# ---------------------------------------------------------
valid_models = []
for strategy_key, result in model_results.items():
    if "error" not in result and not result.get("is_discarded", False):
        income = result["metrics"]["expected_annual_gain_usd"]
        valid_models.append((strategy_key, income, result))

valid_models.sort(key=lambda x: x[1], reverse=True)
top_model_key = valid_models[0][0] if valid_models else None

# ---------------------------------------------------------
# Top Recommendation Hero Banner
# ---------------------------------------------------------
if top_model_key:
    top_info = ALL_STRATEGIES[top_model_key]
    top_res = model_results[top_model_key]
    top_metrics = top_res["metrics"]
    top_risk_label, _ = classify_risk(top_metrics["volatility_pct"])
    st.markdown(
        '<section class="recommendation-card">'
        '<div class="recommendation-label">Top-ranked eligible model · based on expected annual gain</div>'
        f'<div class="recommendation-name">{html.escape(top_info["name"])}</div>'
        '<div class="recommendation-grid">'
        f'<div class="recommendation-metric"><span>Expected annual gain</span><strong>+${top_metrics["expected_annual_gain_usd"]:,.2f}</strong></div>'
        f'<div class="recommendation-metric"><span>Expected annual return</span><strong>{top_metrics["expected_return_pct"]:.2f}%</strong></div>'
        f'<div class="recommendation-metric"><span>Annual volatility · {html.escape(top_risk_label)}</span><strong>{top_metrics["volatility_pct"]:.2f}%</strong></div>'
        '</div></section>',
        unsafe_allow_html=True,
    )
else:
    st.warning(f"No models are currently eligible under the {MAX_ALLOWED_RISK_PCT:.0f}% volatility limit and selected filters.")

# ---------------------------------------------------------
# Display: Model Ranking & Comparison Table
# ---------------------------------------------------------
st.subheader(f"Model comparison · ${budget:,.2f} USD")

metric_display_names = {
    "sharpe": "Sharpe Ratio",
    "sortino": "Sortino Ratio",
    "treynor": "Treynor Ratio"
}
selected_metric_name = metric_display_names.get(selected_metric, "Sharpe Ratio")

summary_rows = []
for strategy_key, info in visible_strategies.items():
    result = model_results.get(strategy_key, {})
    if "error" in result:
        summary_rows.append({
            "Recommendation": "❌ Error",
            "Model": f"{info['icon']} {info['name']}",
            "Est. Annual Profit": "—",
            "Expected Return": "—",
            "Annual Volatility (Risk)": "—",
            "Risk Assessment": "—",
            selected_metric_name: "—",
            "Action Status": f"Error: {result['error'][:100]}"
        })
    elif result.get("is_discarded", False):
        metrics = result["metrics"]
        vol = metrics["volatility_pct"]
        summary_rows.append({
            "Recommendation": "🚫 Discarded",
            "Model": f"{info['icon']} {info['name']}",
            "Est. Annual Profit": f"${metrics['expected_annual_gain_usd']:,.2f}",
            "Expected Return": f"{metrics['expected_return_pct']:.2f}%",
            "Annual Volatility (Risk)": f"{vol:.2f}%",
            "Risk Assessment": f"🔴 Discarded (> {MAX_ALLOWED_RISK_PCT:.0f}%)",
            selected_metric_name: f"{metrics['selected_ratio_value']:.4f}",
            "Action Status": f"Unselectable (Risk > {MAX_ALLOWED_RISK_PCT:.0f}%)"
        })
    else:
        metrics = result["metrics"]
        vol = metrics["volatility_pct"]
        risk_label, _ = classify_risk(vol)
        is_top = (strategy_key == top_model_key)
        rec_tag = "🥇 #1 Top Recommendation" if is_top else "✅ Eligible"
        
        summary_rows.append({
            "Recommendation": rec_tag,
            "Model": f"{info['icon']} {info['name']}",
            "Est. Annual Profit": f"${metrics['expected_annual_gain_usd']:,.2f}",
            "Expected Return": f"{metrics['expected_return_pct']:.2f}%",
            "Annual Volatility (Risk)": f"{vol:.2f}%",
            "Risk Assessment": risk_label,
            selected_metric_name: f"{metrics['selected_ratio_value']:.4f}",
            "Action Status": "Selectable"
        })

summary_df = pd.DataFrame(summary_rows)
st.dataframe(summary_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# Display: Individual Model Cards & IBKR Rebalance
# ---------------------------------------------------------
st.subheader("Model details and allocation")

sorted_models = []
for strategy_key in visible_strategies:
    result = model_results.get(strategy_key, {})
    if "error" in result:
        sorted_models.append((strategy_key, float("-inf"), True))
    elif result.get("is_discarded", False):
        sorted_models.append((strategy_key, result["metrics"]["expected_annual_gain_usd"] - 1e9, True))
    else:
        sorted_models.append((strategy_key, result["metrics"]["expected_annual_gain_usd"], False))

sorted_models.sort(key=lambda x: x[1], reverse=True)

for rank, (strategy_key, _, is_discarded_or_error) in enumerate(sorted_models, 1):
    info = visible_strategies[strategy_key]
    result = model_results.get(strategy_key, {})

    if "error" in result:
        with st.expander(f"❌ {info['icon']} {info['name']} — Error", expanded=False):
            st.error(result["error"])
        continue

    metrics = result["metrics"]
    is_discarded = result.get("is_discarded", False)
    volatility_pct = metrics["volatility_pct"]
    risk_label, _ = classify_risk(volatility_pct)

    is_top = (strategy_key == top_model_key)
    badge = "🥇 TOP RECOMMENDED" if is_top else ("🚫 DISCARDED" if is_discarded else f"#{rank}")

    expander_title = (
        f"{badge} | {info['icon']} {info['name']} — "
        f"Est. Profit: +${metrics['expected_annual_gain_usd']:,.2f}/yr | "
        f"Risk: {volatility_pct:.2f}% ({risk_label})"
    )

    with st.expander(expander_title, expanded=is_top):
        st.caption(info["description"])

        if is_discarded:
            st.warning(
                f"🚫 **Model Discarded & Unselectable:** This model generated an annualized volatility risk of "
                f"**{volatility_pct:.2f}%**, which exceeds the maximum allowable **{MAX_ALLOWED_RISK_PCT:.0f}% Risk Ceiling**.",
                icon="⚠️"
            )

        # Metrics row
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("💰 Est. Annual Profit", f"${metrics['expected_annual_gain_usd']:,.2f}")
        col2.metric("📈 Expected Return", f"{metrics['expected_return_pct']:.2f}%")
        col3.metric("📉 Volatility (Risk)", f"{volatility_pct:.2f}%")
        col4.metric(f"📐 {selected_metric_name}", f"{metrics['selected_ratio_value']:.4f}")
        col5.metric("⚠️ Risk Assessment", risk_label)

        allocations_pct = result.get("allocations_pct", {})
        allocations_usd = result.get("allocations_usd", {})

        # Allocation charts
        if allocations_pct:
            alloc_df = pd.DataFrame([
                {
                    "Ticker": ticker,
                    "Company Name": get_metadata(ticker).company_name,
                    "Country": get_metadata(ticker).country,
                    "Sector": get_metadata(ticker).sector,
                    "P/E Ratio": get_metadata(ticker).pe_ratio if get_metadata(ticker).pe_ratio is not None else "N/A",
                    "Weight (%)": round(weight * 100, 2),
                    "Investment ($)": allocations_usd.get(ticker, 0.0)
                }
                for ticker, weight in allocations_pct.items()
            ]).sort_values(by="Weight (%)", ascending=False)

            chart_col, pie_col = st.columns([3, 2])
            with chart_col:
                fig_bar = px.bar(
                    alloc_df,
                    x="Ticker",
                    y="Investment ($)",
                    text="Investment ($)",
                    title=f"Capital Allocation — {info['name']}",
                    color="Weight (%)",
                    color_continuous_scale=[[0, "#365343"], [1, "#a9df83"]]
                )
                fig_bar.update_traces(texttemplate='$%{text:,.2f}', textposition='outside')
                fig_bar.update_layout(
                    height=380,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font={"family": "DM Sans, sans-serif", "color": "#c6d2cb"},
                    title_font={"color": "#edf4ef"},
                    xaxis={"gridcolor": "#263530", "linecolor": "#263530"},
                    yaxis={"gridcolor": "#263530", "linecolor": "#263530"},
                    coloraxis_colorbar={"tickfont": {"color": "#9aaba2"}, "outlinecolor": "#263530"},
                    margin={"l": 20, "r": 20, "t": 60, "b": 30},
                )
                st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_chart_{strategy_key}")

            with pie_col:
                fig_pie = px.pie(
                    alloc_df,
                    names="Ticker",
                    values="Investment ($)",
                    title="Portfolio Distribution",
                    hole=0.4
                )
                fig_pie.update_traces(
                    marker={"colors": ["#a9df83", "#78b889", "#568f79", "#436c66", "#526e83", "#8290a0", "#b29d72", "#a87365"]},
                    textfont={"color": "#edf4ef"},
                )
                fig_pie.update_layout(
                    height=380,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font={"family": "DM Sans, sans-serif", "color": "#c6d2cb"},
                    title_font={"color": "#edf4ef"},
                    legend={"font": {"color": "#c6d2cb"}},
                    margin={"l": 20, "r": 20, "t": 60, "b": 30},
                )
                st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_chart_{strategy_key}")

            st.dataframe(alloc_df, use_container_width=True, hide_index=True, key=f"df_table_{strategy_key}")

        # ---------------------------------------------------------
        # IBKR REBALANCE BUTTON
        # ---------------------------------------------------------
        st.markdown("---")
        rebalance_col, status_col = st.columns([1, 2])

        with rebalance_col:
            if is_discarded:
                st.error("🚫 Rebalancing Unselectable: Exceeds 40% Risk Ceiling")
            elif ibkr_connected:
                rebalance_key = f"rebalance_{strategy_key}"
                btn_label = f"🏛️ Execute {info['name']} via IBKR" if not is_top else f"🚀 Execute #1 Recommended Portfolio via IBKR"
                if st.button(
                    btn_label,
                    key=rebalance_key,
                    type="primary" if is_top else "secondary",
                    use_container_width=True
                ):
                    with status_col:
                        with st.spinner(f"Executing {info['name']} via IBKR Client Portal Gateway..."):
                            try:
                                exec_result = execute_rebalance(
                                    target_weights=allocations_pct,
                                    budget=budget
                                )
                                st.session_state[f"exec_result_{strategy_key}"] = exec_result
                                st.success(f"✅ IBKR Order submission complete! {len(exec_result)} tickers processed.")
                            except Exception as e:
                                st.error(f"❌ IBKR Execution failed: {str(e)}")
            else:
                st.info("🔒 Connect IBKR Client Portal Gateway (`http://localhost:5000`) to enable live/paper rebalancing", icon="🏛️")

        # Show execution log if active
        exec_key = f"exec_result_{strategy_key}"
        if exec_key in st.session_state:
            st.markdown("**📋 IBKR Order Execution Log:**")
            st.dataframe(st.session_state[exec_key], use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# Footer: IBKR Account Overview
# ---------------------------------------------------------
if ibkr_connected:
    st.markdown("---")
    st.subheader("🏛️ Interactive Brokers (IBKR) Account Overview")
    try:
        acc_info = get_account_info()
        acol1, acol2, acol3 = st.columns(3)
        acol1.metric("Active Account ID", str(acc_info.get("account_id", "N/A")))
        acol2.metric("Portfolio Value", f"${acc_info.get('portfolio_value', 0.0):,.2f}")
        acol3.metric("Buying Power", f"${acc_info.get('buying_power', 0.0):,.2f}")

        positions_df = get_current_positions()
        if not positions_df.empty:
            st.markdown("**Current IBKR Positions:**")
            st.dataframe(positions_df, use_container_width=True, hide_index=True)
        else:
            st.info("No open positions found in IBKR account.")
    except Exception as e:
        st.warning(f"Could not load IBKR account data: {e}")
