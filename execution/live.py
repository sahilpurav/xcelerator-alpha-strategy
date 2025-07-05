import time
from datetime import timedelta
from typing import Optional

import pandas as pd

from broker.zerodha import ZerodhaBroker
from data.price_fetcher import download_and_cache_prices
from data.universe_fetcher import get_universe_symbols
from logic.display import display_execution_plan
from logic.filters import apply_universe_filters
from logic.planner import plan_rebalance
from logic.strategy import run_strategy
from utils.market import get_last_trading_date, get_ranking_date


def _get_filtered_universe() -> list[str]:
    """
    Fetches the universe of symbols, applies filters, and returns the filtered list.
    """
    universe = get_universe_symbols("nifty500")
    return apply_universe_filters(universe)


def _get_latest_prices(symbols: list[str], as_of_date: pd.Timestamp) -> dict:
    """
    Fetches stock prices for the given symbols from the start of the year to the as_of_date.
    """
    start = (as_of_date - timedelta(days=400)).strftime("%Y-%m-%d")
    end = as_of_date.strftime("%Y-%m-%d")
    return download_and_cache_prices(symbols, start=start, end=end)


def _execute_orders(
    exec_df: pd.DataFrame, broker: ZerodhaBroker, dry_run: bool = False
):
    """
    Executes the given execution plan using the broker API.
    SELLs are executed first, followed by BUYs.
    """
    print("-" * 65)
    print("📋 Order Summary")
    print("-" * 65)
    for action in ["SELL", "BUY"]:
        df_action = exec_df.query(f"Action == '{action}'")
        for _, row in df_action.iterrows():
            symbol = row["Symbol"]
            quantity = int(row["Quantity"])
            if quantity <= 0:
                continue

            print(
                f"{'🔻' if action == 'SELL' else '🔺'} {action} {symbol}: Qty = {quantity}"
            )
            if not dry_run:
                try:
                    print("\n📡 Placing live orders via broker...")
                    broker.place_market_order(symbol, quantity, transaction_type=action)
                    time.sleep(1)  # Avoid hitting API rate limits
                except Exception as e:
                    print(f"❌ Failed to {action} {symbol}: {e}")


def _override_ranked_stocks_with_broker_prices(symbols, price_data, broker):
    """
    Overrides the price data with the latest prices from the broker for the given symbols.

    Args:
        symbols (list): List of stock symbols to override prices for.
        price_data (dict): Current price data dictionary.
        broker: Instance of the Broker to fetch live prices.

    Returns:
        dict: Updated price data with broker prices.
    """
    try:
        live_prices = broker.ltp(symbols)
        for symbol in symbols:
            if symbol not in live_prices:
                continue

            symbol_with_ns = f"{symbol}.NS"
            if symbol_with_ns not in price_data:
                continue

            latest_date = price_data[symbol_with_ns].index.max()
            price_data[symbol_with_ns].loc[latest_date, "Close"] = live_prices[symbol]

    except Exception as e:
        print(f"❌ Failed to fetch live prices: {e}")

    return price_data


def run_rebalance(
    top_n: int = 15,
    band: int = 5,
    cash_equivalent: str = "LIQUIDCASE.NS",
    rank_day: Optional[str] = None,
    dry_run: bool = False,
):
    """
    Executes a rebalancing strategy that adapts to market conditions.

    In STRONG market regime:
    - Invests in top N ranked stocks based on momentum
    - Maintains positions in stocks that fall within top N + band rankings
    - Sells stocks that fall outside the top N + band range

    In WEAK market regime:
    - Moves entire portfolio to cash equivalent position

    When market transitions from WEAK to STRONG:
    - Redeploys capital into top N ranked stocks

    Args:
        top_n (int): Target number of stocks in portfolio
        band (int): Band size for portfolio stability
        cash_equivalent (str): Symbol to use as cash equivalent
        rank_day (str, optional): Day of week for ranking (Monday, Tuesday, Wednesday, etc.).
                                 If None, uses the latest trading day for both ranking and execution.
        dry_run (bool): If True, simulates execution without placing orders
    """

    exec_date = pd.to_datetime(get_last_trading_date())
    ranking_date = pd.to_datetime(get_ranking_date(rank_day))

    print(f"\n🔄 Running weekly rebalance strategy as of {exec_date.date()}...")
    if ranking_date != exec_date:
        print(
            f"📊 Using rankings from {ranking_date.date()} (last {rank_day or 'trading day'})"
        )

    universe = _get_filtered_universe()
    universe_symbols = [f"{s}.NS" for s in universe]

    price_symbols = list(set(universe_symbols + [cash_equivalent, "^CRSLDX"]))
    price_data = _get_latest_prices(price_symbols, exec_date)

    broker = ZerodhaBroker()
    previous_holdings = broker.get_holdings()
    held_symbols = [h["symbol"] for h in previous_holdings]

    # Create lookup for previous holdings quantities
    holdings_lookup = {h["symbol"]: h for h in previous_holdings}

    recommendations = run_strategy(
        price_data,
        ranking_date,
        held_symbols,
        top_n,
        band,
        cash_equivalent=cash_equivalent,
    )

    # Get all symbols from recommendations for price updates
    all_symbols = [rec["symbol"] for rec in recommendations]
    price_data = _override_ranked_stocks_with_broker_prices(
        all_symbols, price_data, broker
    )

    # Initialize the three lists
    held_stocks = []
    new_stocks = []
    removed_stocks = []

    # Process each recommendation
    for stock in recommendations:
        symbol = stock["symbol"]
        action = stock["action"]
        rank = stock["rank"]  # Rank is now embedded in the recommendation
        symbol_with_ns = f"{symbol}.NS"

        # Skip if no price data available
        if symbol_with_ns not in price_data:
            continue

        # Get last price
        last_price = price_data[symbol_with_ns].iloc[-1]["Close"]

        # Get quantity from previous holdings (0 if not held)
        quantity = holdings_lookup.get(symbol, {}).get("quantity", 0)

        # Create stock entry based on action
        stock_entry = {
            "symbol": symbol,
            "quantity": quantity if action in ["HOLD", "SELL"] else 0,
            "last_price": last_price,
            "rank": rank,
        }

        # Add to appropriate list
        if action == "BUY":
            new_stocks.append(stock_entry)
        elif action == "HOLD":
            held_stocks.append(stock_entry)
        elif action == "SELL":
            removed_stocks.append(stock_entry)

    # Get cash from broker
    cash = broker.cash()

    # Plan smart rebalance
    exec_df = plan_rebalance(
        held_stocks=held_stocks,
        new_stocks=new_stocks,
        removed_stocks=removed_stocks,
        cash=cash,
    )

    display_execution_plan(exec_df, "rebalance", cash=cash)
    _execute_orders(exec_df, broker, dry_run=dry_run)


def run_topup(dry_run: bool = False):
    """
    Adds capital to the existing portfolio by executing a market order for the cash equivalent.

    Args:
        dry_run (bool): If True, simulates execution without placing orders
    """
    broker = ZerodhaBroker()
    raw_holdings = broker.get_holdings()

    # Transform holdings structure: remove buy_price and add rank with None value
    held_stocks = []
    for holding in raw_holdings:
        held_stocks.append(
            {
                "symbol": holding["symbol"],
                "quantity": holding["quantity"],
                "last_price": holding["last_price"],
                "rank": None,
            }
        )

    cash = broker.cash()

    print(f"\n💰 Adding ₹{cash} to portfolio...")

    exec_df = plan_rebalance(
        held_stocks=held_stocks,
        new_stocks=[],
        removed_stocks=[],
        cash=cash,
    )

    # Remove Action="HOLD" rows from exec_df
    exec_df = exec_df[exec_df["Action"] != "HOLD"]

    display_execution_plan(exec_df, "rebalance", cash=cash)
    _execute_orders(exec_df, broker, dry_run=dry_run)
