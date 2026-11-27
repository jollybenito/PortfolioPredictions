"""
alpaca_executor.py — Execute portfolio rebalancing via Alpaca API.

Reads portfolio weights and places buy/sell orders to match target allocations.
Works 100% in the cloud — no gateway, no VPS, just REST API calls.

Usage:
    # From code:
    from alpaca_executor import execute_rebalance
    result = execute_rebalance(weights_dict, budget=10000, paper=True)
    
    # CLI:
    python alpaca_executor.py --weights weights.csv --budget 10000 --paper
"""
import os
import pandas as pd
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


def _get_client(paper: bool = True):
    """Create an Alpaca TradingClient. Raises ImportError with install instructions."""
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        raise ImportError(
            "alpaca-py is required for live trading. Install with:\n"
            "  pip install alpaca-py"
        )

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        raise ValueError(
            "Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env file.\n"
            "Get your keys at https://app.alpaca.markets/paper/dashboard/overview"
        )

    return TradingClient(api_key, secret_key, paper=paper)


def get_account_info(paper: bool = True) -> Dict:
    """Return account summary (cash, equity, buying power)."""
    client = _get_client(paper)
    account = client.get_account()
    return {
        "cash": float(account.cash),
        "portfolio_value": float(account.portfolio_value),
        "buying_power": float(account.buying_power),
        "currency": account.currency,
        "status": account.status,
        "paper": paper
    }


def get_current_positions(paper: bool = True) -> pd.DataFrame:
    """Return current portfolio positions as a DataFrame."""
    client = _get_client(paper)
    positions = client.get_all_positions()

    if not positions:
        return pd.DataFrame(columns=["symbol", "qty", "market_value",
                                      "avg_entry_price", "current_price",
                                      "unrealized_pl", "unrealized_plpc"])

    rows = []
    for pos in positions:
        rows.append({
            "symbol": pos.symbol,
            "qty": float(pos.qty),
            "market_value": float(pos.market_value),
            "avg_entry_price": float(pos.avg_entry_price),
            "current_price": float(pos.current_price),
            "unrealized_pl": float(pos.unrealized_pl),
            "unrealized_plpc": round(float(pos.unrealized_plpc) * 100, 2)
        })
    return pd.DataFrame(rows)


def execute_rebalance(
    target_weights: Dict[str, float],
    budget: float,
    paper: bool = True,
    min_order_value: float = 1.00
) -> pd.DataFrame:
    """
    Rebalance portfolio to match target weights via Alpaca API.

    Args:
        target_weights: {'AAPL': 0.15, 'MSFT': 0.20, ...} must sum to ~1.0
        budget: Total capital to allocate ($)
        paper: Use paper trading (True) or live (False)
        min_order_value: Skip orders smaller than this amount ($)

    Returns:
        DataFrame with order results for each ticker
    """
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    client = _get_client(paper)

    # Get current positions
    current_positions = {}
    try:
        for pos in client.get_all_positions():
            current_positions[pos.symbol] = {
                "qty": float(pos.qty),
                "market_value": float(pos.market_value),
                "current_price": float(pos.current_price)
            }
    except Exception:
        pass  # No positions yet

    results = []

    for ticker, weight in target_weights.items():
        if weight < 0.0001:
            continue  # Skip zero-weight assets

        # Skip non-US tickers (Chinese stocks like .SS, .SZ won't work on Alpaca)
        if "." in ticker and not ticker.replace("-", "").isalpha():
            results.append({
                "ticker": ticker,
                "action": "SKIP",
                "target_value": round(budget * weight, 2),
                "order_value": 0,
                "order_id": None,
                "status": "Unsupported (non-US ticker)"
            })
            continue

        target_value = budget * weight
        current_data = current_positions.get(ticker, {})
        current_value = current_data.get("market_value", 0.0)

        diff_value = target_value - current_value

        if abs(diff_value) < min_order_value:
            results.append({
                "ticker": ticker,
                "action": "HOLD",
                "target_value": round(target_value, 2),
                "order_value": 0,
                "order_id": None,
                "status": "Already at target"
            })
            continue

        side = OrderSide.BUY if diff_value > 0 else OrderSide.SELL

        try:
            order_data = MarketOrderRequest(
                symbol=ticker,
                notional=round(abs(diff_value), 2),
                side=side,
                time_in_force=TimeInForce.DAY
            )

            order = client.submit_order(order_data=order_data)
            results.append({
                "ticker": ticker,
                "action": side.value,
                "target_value": round(target_value, 2),
                "order_value": round(abs(diff_value), 2),
                "order_id": str(order.id),
                "status": str(order.status)
            })
        except Exception as e:
            results.append({
                "ticker": ticker,
                "action": side.value,
                "target_value": round(target_value, 2),
                "order_value": round(abs(diff_value), 2),
                "order_id": None,
                "status": f"ERROR: {str(e)}"
            })

    return pd.DataFrame(results)


def check_alpaca_configured() -> bool:
    """Check if Alpaca API keys are configured in .env."""
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    return bool(api_key and secret_key)


def check_alpaca_connection(paper: bool = True) -> tuple:
    """
    Test Alpaca connection. Returns (success: bool, message: str).
    """
    if not check_alpaca_configured():
        return False, "API keys not configured. Add ALPACA_API_KEY and ALPACA_SECRET_KEY to .env"

    try:
        info = get_account_info(paper=paper)
        return True, f"Connected — Cash: ${info['cash']:,.2f}, Portfolio: ${info['portfolio_value']:,.2f}"
    except ImportError:
        return False, "alpaca-py not installed. Run: pip install alpaca-py"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


# ------------------------------------
# CLI entry point
# ------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Execute portfolio via Alpaca API")
    parser.add_argument("--weights", default="weights.csv", help="Path to weights CSV (ticker,weight)")
    parser.add_argument("--budget", type=float, default=10000, help="Total capital to allocate")
    parser.add_argument("--live", action="store_true", help="Use live trading (default: paper)")
    args = parser.parse_args()

    paper = not args.live

    # Load weights
    w_df = pd.read_csv(args.weights, header=None, names=["ticker", "weight"])
    weights_dict = dict(zip(w_df["ticker"], w_df["weight"].astype(float)))
    weights_dict = {k: v for k, v in weights_dict.items() if v > 0.0001}

    print(f"\n{'='*50}")
    print(f"Alpaca Portfolio Executor ({'PAPER' if paper else '🔴 LIVE'})")
    print(f"Budget: ${args.budget:,.2f}")
    print(f"Active tickers: {len(weights_dict)}")
    print(f"{'='*50}\n")

    result = execute_rebalance(weights_dict, args.budget, paper=paper)
    print(result.to_string(index=False))
    result.to_csv("execution_log.csv", index=False)
    print("\nResults saved to execution_log.csv")
