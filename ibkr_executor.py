"""
ibkr_executor.py — Automated Portfolio Execution via Interactive Brokers (IBKR) REST API.

Communicates directly with the IBKR Client Portal Gateway REST API.
Supports individual accounts, paper trading accounts, and Advisor Master accounts with FA group allocations.

Default Gateway Endpoint: http://localhost:5000/v1/api (or https://localhost:5000/v1/api)
"""
import os
import requests
import json
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# Suppress self-signed certificate warnings from local Client Portal Gateway
requests.packages.urllib3.disable_warnings()


def get_gateway_url() -> str:
    """Return base IBKR Client Portal Gateway URL from environment or default."""
    base_url = os.getenv("IBKR_GATEWAY_URL", "http://localhost:5000").rstrip("/")
    if not base_url.endswith("/v1/api"):
        base_url += "/v1/api"
    return base_url


def check_ibkr_configured() -> bool:
    """Check if IBKR Gateway URL is configured."""
    return bool(get_gateway_url())


def check_ibkr_connection() -> Tuple[bool, str]:
    """
    Test connection to local/cloud IBKR Client Portal Gateway.
    Returns (success: bool, message: str).
    """
    url = f"{get_gateway_url()}/iserver/auth/status"
    try:
        resp = requests.get(url, verify=False, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            authenticated = data.get("authenticated", False)
            connected = data.get("connected", False)
            if authenticated and connected:
                return True, "Connected & Authenticated to IBKR Gateway"
            elif authenticated:
                return True, "Authenticated (Connecting to IBKR servers...)"
            else:
                return False, "Gateway responding, but NOT authenticated. Please log into IBKR Client Portal Gateway."
        else:
            return False, f"Gateway error: HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to IBKR Gateway (Connection Refused). Ensure Gateway is running on http://localhost:5000"
    except Exception as e:
        return False, f"Connection error: {str(e)}"


def get_accounts() -> List[Dict]:
    """Fetch list of available IBKR accounts (Individual, Paper, or Advisor Master/Sub-accounts)."""
    url = f"{get_gateway_url()}/portfolio/accounts"
    try:
        resp = requests.get(url, verify=False, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


def get_account_info(account_id: Optional[str] = None) -> Dict:
    """
    Fetch account summary (cash, portfolio value, buying power).
    If no account_id provided, uses IBKR_ACCOUNT_ID env var or first available account.
    """
    accounts = get_accounts()
    if not accounts:
        return {"error": "No active IBKR accounts found."}

    target_acc = account_id or os.getenv("IBKR_ACCOUNT_ID") or accounts[0].get("accountId")

    url = f"{get_gateway_url()}/portfolio/{target_acc}/summary"
    try:
        resp = requests.get(url, verify=False, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            
            # Extract key values from IBKR summary array format
            summary = {"account_id": target_acc}
            if isinstance(data, list):
                for item in data:
                    key = item.get("desc", "").lower()
                    val = item.get("value")
                    if "total cash" in key or "netliquidation" in key:
                        summary["portfolio_value"] = float(val) if val else 0.0
                    elif "cash" in key:
                        summary["cash"] = float(val) if val else 0.0
                    elif "buyingpower" in key or "buying power" in key:
                        summary["buying_power"] = float(val) if val else 0.0

            summary.setdefault("cash", 0.0)
            summary.setdefault("portfolio_value", 0.0)
            summary.setdefault("buying_power", 0.0)
            return summary
        return {"error": f"Failed to fetch account summary (HTTP {resp.status_code})"}
    except Exception as e:
        return {"error": str(e)}


def get_current_positions(account_id: Optional[str] = None) -> pd.DataFrame:
    """Fetch current positions for specified account."""
    accounts = get_accounts()
    if not accounts:
        return pd.DataFrame()

    target_acc = account_id or os.getenv("IBKR_ACCOUNT_ID") or accounts[0].get("accountId")
    url = f"{get_gateway_url()}/portfolio/{target_acc}/positions/0"

    try:
        resp = requests.get(url, verify=False, timeout=5)
        if resp.status_code == 200:
            positions = resp.json()
            if not positions or not isinstance(positions, list):
                return pd.DataFrame()

            rows = []
            for pos in positions:
                rows.append({
                    "conid": pos.get("conid"),
                    "symbol": pos.get("contractDesc") or pos.get("ticker"),
                    "qty": float(pos.get("position", 0)),
                    "market_value": float(pos.get("mktValue", 0)),
                    "avg_cost": float(pos.get("avgCost", 0)),
                    "mkt_price": float(pos.get("mktPrice", 0)),
                    "unrealized_pnl": float(pos.get("unrealizedPnl", 0))
                })
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def search_contract_id(ticker: str) -> Optional[int]:
    """
    Search IBKR secdef for a ticker to obtain its unique Contract ID (`conid`).
    Supports US equities, ADRs, and international stocks.
    """
    # Sanitize ticker (e.g. remove exchange suffix if searching base symbol)
    base_ticker = ticker.split(".")[0]
    url = f"{get_gateway_url()}/iserver/secdef/search"

    try:
        resp = requests.post(
            url,
            json={"symbol": base_ticker, "name": True, "secType": "STK"},
            verify=False,
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                # Return the first matching stock contract ID
                for item in data:
                    if item.get("secType") == "STK":
                        return item.get("conid")
                return data[0].get("conid")
    except Exception:
        pass
    return None


def execute_rebalance(
    target_weights: Dict[str, float],
    budget: float,
    account_id: Optional[str] = None,
    fa_group: Optional[str] = None,
    fa_method: str = "NetLiq"
) -> pd.DataFrame:
    """
    Rebalance portfolio via IBKR Client Portal REST API.

    Args:
        target_weights: {'AAPL': 0.20, 'MSFT': 0.30, ...}
        budget: Total capital to allocate ($)
        account_id: Target account ID (or uses IBKR_ACCOUNT_ID)
        fa_group: Optional Financial Advisor Group name (e.g., 'AllClients') for Advisor Master accounts
        fa_method: FA allocation method ('NetLiq', 'EqualQuantity', 'AvailableEquity')

    Returns:
        DataFrame with execution results for each ticker
    """
    accounts = get_accounts()
    target_acc = account_id or os.getenv("IBKR_ACCOUNT_ID")
    if not target_acc and accounts:
        target_acc = accounts[0].get("accountId")

    if not target_acc:
        raise ValueError("No valid IBKR account ID found. Ensure Gateway is connected.")

    results = []

    for ticker, weight in target_weights.items():
        if weight < 0.0001:
            continue

        target_dollar = budget * weight

        # Resolve IBKR Contract ID (conid)
        conid = search_contract_id(ticker)
        if not conid:
            results.append({
                "ticker": ticker,
                "conid": "N/A",
                "action": "SKIP",
                "target_value": round(target_dollar, 2),
                "status": "Contract ID (conid) not found on IBKR"
            })
            continue

        # Prepare Order Payload
        order_payload = {
          "orders": [
            {
              "conid": conid,
              "orderType": "MKT",
              "side": "BUY",
              "cashQty": round(target_dollar, 2),
              "tif": "DAY"
            }
          ]
        }

        # Attach FA Group details if using Advisor Master account
        if fa_group:
            order_payload["orders"][0]["faGroup"] = fa_group
            order_payload["orders"][0]["faMethod"] = fa_method

        order_url = f"{get_gateway_url()}/iserver/account/{target_acc}/orders"

        try:
            resp = requests.post(order_url, json=order_payload, verify=False, timeout=6)
            if resp.status_code in [200, 201]:
                res_data = resp.json()
                results.append({
                    "ticker": ticker,
                    "conid": conid,
                    "action": "BUY",
                    "target_value": round(target_dollar, 2),
                    "status": "Order Placed / Submitted"
                })
            else:
                results.append({
                    "ticker": ticker,
                    "conid": conid,
                    "action": "BUY",
                    "target_value": round(target_dollar, 2),
                    "status": f"HTTP {resp.status_code}: {resp.text[:60]}"
                })
        except Exception as e:
            results.append({
                "ticker": ticker,
                "conid": conid,
                "action": "BUY",
                "target_value": round(target_dollar, 2),
                "status": f"Error: {str(e)}"
            })

    return pd.DataFrame(results)


if __name__ == "__main__":
    print(f"Testing IBKR Gateway Connection at {get_gateway_url()}...")
    ok, msg = check_ibkr_connection()
    print(f"Connection Status: {msg}")
    if ok:
        accs = get_accounts()
        print(f"Available Accounts: {accs}")
