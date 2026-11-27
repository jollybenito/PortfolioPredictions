import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sys
from datetime import datetime

# Ensure src modules can be resolved
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.application.portfolio_calculation_use_case import PortfolioCalculationUseCase
from src.domain.models.stock_metadata import get_metadata

# ---------------------------------------------------------
# Streamlit Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Portfolio Optimization ML Engine",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📈 Machine Learning Portfolio Optimization Engine")
st.markdown("""
*Interactive Machine Learning & Quantitative Portfolio Optimization Platform.*  
Set your investment budget, choose a portfolio strategy, adjust risk tolerance, and mass-exclude stock groups or individual assets to dynamically recalculate capital allocations ($) and performance statistics.
""")

# ---------------------------------------------------------
# Load Data & Dependencies
# ---------------------------------------------------------
def get_use_case():
    """Build the application against its PostgreSQL-backed repository."""
    from src.adapters.persistence.sql_repository import SQLStockPriceRepository
    repo = SQLStockPriceRepository()
    return PortfolioCalculationUseCase(stock_repo=repo), "sql"

def get_last_etl_timestamp() -> str:
    try:
        from database import get_db_session, ETLMetadata
        session = get_db_session()
        try:
            record = session.query(ETLMetadata).filter(ETLMetadata.key == "daily_market_update").first()
            if not record:
                record = session.query(ETLMetadata).filter(ETLMetadata.key == "last_full_etl_run").first()
            if record and record.value:
                dt = datetime.fromisoformat(record.value)
                return dt.strftime("%B %d, %Y at %I:%M %p UTC")
        finally:
            session.close()
    except Exception:
        pass
    return "Unknown"

use_case, _ = get_use_case()
try:
    returns_df = use_case.stock_repo.get_returns_df()
except Exception as exc:
    st.error(f"Could not load market data from PostgreSQL: {exc}")
    st.stop()
last_etl = get_last_etl_timestamp()

if returns_df.empty:
    st.error("No historical return data available. Please initialize PostgreSQL and run the market data ETL pipeline.")
    st.stop()

st.caption(f"⚠️ **Disclaimer:** Market data is not live. Last market data update: **{last_etl}**. This model is designed for long-term investment analysis and is not intended for real-time trading.")

all_available_tickers = sorted(returns_df.columns.tolist())

# Extract available metadata groups dynamically
available_countries = sorted(list(set(get_metadata(t).country for t in all_available_tickers)))
available_sectors = sorted(list(set(get_metadata(t).sector for t in all_available_tickers if get_metadata(t).sector != "Unknown")))
available_exchanges = sorted(list(set(get_metadata(t).exchange for t in all_available_tickers)))

# ---------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------
st.sidebar.header("🎯 Investment & Strategy Inputs")

# 1. Budget Input ($200 to $999,999,999)
st.sidebar.subheader("💰 Investment Budget ($ USD)")
budget = st.sidebar.number_input(
    "Total Capital to Invest:",
    min_value=200.0,
    max_value=999_999_999.0,
    value=10_000.0,
    step=100.0,
    format="%.2f",
    help="Enter investment amount between $200 and $999,999,999 USD"
)

# 2. Strategy Selection
st.sidebar.subheader("⚙️ Portfolio Strategy")
strategy_option = st.sidebar.selectbox(
    "Select Strategy Model",
    options=[
        ("Hierarchical Risk Parity (HRP)", "hrp"),
        ("Mean-Variance (Max Sharpe)", "mean_variance"),
        ("Global Minimum Variance", "min_variance"),
        ("Congressional Trade Signals (Copy-Portfolio)", "political"),
        ("Sovereign Stability & Governance Index (SSGI)", "sovereign_stability")
    ],
    format_func=lambda x: x[0]
)
strategy = strategy_option[1]

# 3. Risk Level Selection (Target Volatility Percentage)
st.sidebar.subheader("⚖️ Target Volatility / Risk Tolerance (%)")
if strategy in ["hrp", "mean_variance", "min_variance"]:
    risk_level = st.sidebar.slider(
        "Target Annual Risk (Volatility %):",
        min_value=5.0,
        max_value=35.0,
        value=15.0,
        step=1.0,
        format="%.1f%%",
        help="Specify the target annualized volatility percentage for portfolio optimization."
    )
else:
    risk_level = 15.0
    st.sidebar.info("Risk adjustment is fixed for heuristic signal-driven strategies.")

# 3b. Risk-Adjusted Metric Selection
st.sidebar.subheader("📐 Risk-Adjusted Performance Metric")
metric_descriptions = {
    "Sharpe Ratio — measures risk-adjusted return relative to total volatility (upside + downside)": "sharpe",
    "Sortino Ratio — measures risk-adjusted return relative to downside risk only": "sortino",
    "Treynor Ratio — measures risk-adjusted return relative to market (systematic) risk (beta)": "treynor"
}
selected_metric_label = st.sidebar.radio(
    "Select ratio for optimization evaluation:",
    options=list(metric_descriptions.keys()),
    index=0,
    help="Choose the risk-adjusted metric used to evaluate portfolio quality.\n\n"
         "• **Sharpe**: Penalizes ALL volatility (up and down).\n"
         "• **Sortino**: Only penalizes downside moves — better for asymmetric return profiles.\n"
         "• **Treynor**: Measures excess return per unit of market risk (beta) — useful for diversified portfolios."
)
selected_metric = metric_descriptions[selected_metric_label]

# 4. Group Exclusion Menu (Country, Sector, Exchange)
st.sidebar.markdown("---")
st.sidebar.subheader("🌍 Group Exclusions (Mass Filter)")
st.sidebar.markdown("*Filter out entire categories of assets by market metadata:*")

excluded_countries = st.sidebar.multiselect(
    "Exclude Markets by Country:",
    options=available_countries,
    default=[],
    help="Select countries (e.g., China, USA) to exclude all stocks domiciled there."
)

excluded_sectors = st.sidebar.multiselect(
    "Exclude Sectors:",
    options=available_sectors,
    default=[],
    help="Select sectors (e.g., Technology, Financial Services) to mass-exclude."
)

excluded_exchanges = st.sidebar.multiselect(
    "Exclude Stock Exchanges:",
    options=available_exchanges,
    default=[],
    help="Select specific exchanges (e.g., SSE, NASDAQ) to exclude."
)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Fundamental Exclusions (P/E Ratio)")
max_pe_input = st.sidebar.number_input(
    "Maximum Allowed P/E Ratio:",
    min_value=0.0,
    max_value=500.0,
    value=0.0,
    step=5.0,
    help="Set maximum Price-to-Earnings ratio. Set to 0 to disable filter. Stocks missing P/E data are treated as extreme cases and excluded when active."
)
max_pe_ratio = max_pe_input if max_pe_input > 0 else None

# 5. Individual Stock Exclusion Menu
st.sidebar.markdown("---")
st.sidebar.subheader("🚫 Individual Stock Exclusions")
excluded_tickers = st.sidebar.multiselect(
    "Exclude specific assets:",
    options=all_available_tickers,
    default=[],
    help="Select individual tickers to exclude from recalculation."
)

# ---------------------------------------------------------
# Recalculate Portfolio
# ---------------------------------------------------------
try:
    result = use_case.calculate_custom_portfolio(
        strategy=strategy,
        budget=budget,
        risk_level=risk_level,
        excluded_tickers=excluded_tickers,
        excluded_countries=excluded_countries,
        excluded_sectors=excluded_sectors,
        excluded_exchanges=excluded_exchanges,
        max_pe_ratio=max_pe_ratio,
        metric=selected_metric
    )

    metrics = result["metrics"]
    allocations_pct = result["allocations_pct"]
    allocations_usd = result["allocations_usd"]

    # ---------------------------------------------------------
    # Key Performance Metrics Cards
    # ---------------------------------------------------------
    st.subheader(f"📊 Portfolio Overview for ${budget:,.2f} USD")
    metric_display_names = {"sharpe": "Sharpe Ratio", "sortino": "Sortino Ratio", "treynor": "Treynor Ratio"}
    selected_metric_name = metric_display_names.get(metrics.get('selected_metric', 'sharpe'), 'Sharpe Ratio')
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Investment Capital", f"${budget:,.2f}")
    col2.metric("Expected Annual Return", f"{metrics['expected_return_pct']:.2f}%", f"+${metrics['expected_annual_gain_usd']:,.2f}/yr")
    col3.metric("Annual Volatility (Risk)", f"{metrics['volatility_pct']:.2f}%")
    col4.metric(selected_metric_name, f"{metrics['selected_ratio_value']:.2f}")

    # ---------------------------------------------------------
    # Visualizations: Allocation Bar Chart & Capital Distribution
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("💼 Capital & Asset Allocations")
    
    if allocations_pct:
        alloc_df = pd.DataFrame([
            {
                "Ticker": ticker,
                "Company Name": get_metadata(ticker).company_name,
                "Country": get_metadata(ticker).country,
                "Sector": get_metadata(ticker).sector,
                "P/E Ratio": get_metadata(ticker).pe_ratio if get_metadata(ticker).pe_ratio is not None else "N/A (Extreme)",
                "Weight (%)": round(weight * 100, 2),
                "Investment ($)": allocations_usd.get(ticker, 0.0)
            }
            for ticker, weight in allocations_pct.items()
        ]).sort_values(by="Weight (%)", ascending=False)

        c1, c2 = st.columns([3, 2])
        with c1:
            fig_bar = px.bar(
                alloc_df,
                x="Ticker",
                y="Investment ($)",
                text="Investment ($)",
                title="Capital Allocation per Asset ($ USD)",
                color="Weight (%)",
                color_continuous_scale="Viridis"
            )
            fig_bar.update_traces(texttemplate='$%{text:,.2f}', textposition='outside')
            st.plotly_chart(fig_bar, use_container_width=True)

        with c2:
            fig_pie = px.pie(
                alloc_df,
                names="Ticker",
                values="Investment ($)",
                title="Portfolio Capital Distribution",
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("📋 Detailed Holdings Table (With Metadata)")
        # Display clean dataframe without style formatting errors on mixed string/float columns
        st.dataframe(
            alloc_df,
            use_container_width=True
        )

    else:
        st.warning("No assets allocated under current group/individual constraints.")

except Exception as err:
    st.error(f"Calculation Error: {err}")
