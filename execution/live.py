import pandas as pd
import os
import time
from typing import Optional
from data.universe_fetcher import get_universe_symbols
from logic.filters import apply_universe_filters
from data.price_fetcher import download_and_cache_prices
from datetime import timedelta
from utils.market import get_last_trading_date, get_ranking_date
from logic.strategy import run_strategy
from utils.cache import save_to_file
from logic.planner import (
    plan_portfolio_rebalance, 
    plan_equity_investment, 
    plan_capital_addition, 
    plan_move_to_cash_equivalent,
    plan_capital_withdrawal
)
from logic.display import display_execution_plan
from broker.zerodha import ZerodhaBroker

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

def _execute_orders(exec_df: pd.DataFrame, broker: ZerodhaBroker, dry_run: bool = False):
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

            print(f"{'🔻' if action == 'SELL' else '🔺'} {action} {symbol}: Qty = {quantity}")
            if not dry_run:
                try:
                    print("\n📡 Placing live orders via broker...")
                    broker.place_market_order(symbol, quantity, transaction_type=action)
                    time.sleep(1)  # Avoid hitting API rate limits
                except Exception as e:
                    print(f"❌ Failed to {action} {symbol}: {e}")


    
def run_topup_only(amount: float, dry_run = False):
    """
    Distributes new capital equally across currently held stocks.
    No ranking, no sells — just top-up.

    Args:
        amount (float): Total additional capital to be distributed across held stocks.
        dry_run (bool): If True, simulates the execution without placing live orders.
    
    Workflow:
        1. Retrieves the last trading day and prints it.
        2. Fetches current holdings from the broker.
        3. If no holdings found, prompts user to run initial investment first.
        4. Gets latest prices for held stocks.
        5. Plans top-up investment based on current holdings and new capital.
        6. Displays execution plan to the user.
        7. Executes orders if not in preview mode.
    """
    as_of_date = pd.to_datetime(get_last_trading_date())
    print(f"\n💰 Running capital top-up strategy as of {as_of_date.date()}...")

    broker = ZerodhaBroker()
    previous_holdings = broker.get_holdings()

    if not previous_holdings:
        print("⚠️ No holdings found. Use `initial` command to start portfolio.")
        return
    
    held_symbols = [h["symbol"] for h in previous_holdings]
    symbols = [f"{s}.NS" for s in held_symbols]
    price_data = _get_latest_prices(symbols, as_of_date)
    
    exec_df = plan_capital_addition(
        previous_holdings=previous_holdings,
        price_data=price_data,
        as_of_date=as_of_date,
        additional_capital=amount
    )

    display_execution_plan(exec_df, "top-up")
    _execute_orders(exec_df, broker, dry_run)

def run_withdraw(
    amount: Optional[float] = None,
    percentage: Optional[float] = None,
    full: bool = False,
    dry_run: bool = False
):
    """
    Withdraws capital from the portfolio proportionally across all holdings.
    
    Args:
        amount (float, optional): Specific amount to withdraw (₹)
        percentage (float, optional): Percentage of portfolio to withdraw (1-100)
        full (bool): If True, withdraws entire portfolio (overrides amount/percentage)
        dry_run (bool): If True, simulates the execution without placing live orders
        
    Workflow:
        1. Retrieves the last trading day
        2. Fetches current holdings from the broker
        3. If no holdings, notifies user and exits
        4. Gets latest prices for held stocks
        5. Plans withdrawal based on parameters
        6. Displays execution plan
        7. Executes orders if not in dry run mode
    """
    as_of_date = pd.to_datetime(get_last_trading_date())
    print(f"\n💸 Running capital withdrawal strategy as of {as_of_date.date()}...")
    
    # Input validation
    if not full and amount is None and percentage is None:
        print("⚠️ Must specify either amount, percentage or full withdrawal.")
        return
    
    if percentage is not None and (percentage <= 0 or percentage > 100):
        print("⚠️ Percentage must be between 1 and 100.")
        return
        
    broker = ZerodhaBroker()
    previous_holdings = broker.get_holdings()

    if not previous_holdings:
        print("⚠️ No holdings found. Nothing to withdraw.")
        return
    
    held_symbols = [h["symbol"] for h in previous_holdings]
    symbols = [f"{s}.NS" for s in held_symbols]
    price_data = _get_latest_prices(symbols, as_of_date)
    
    exec_df = plan_capital_withdrawal(
        previous_holdings=previous_holdings,
        price_data=price_data,
        as_of_date=as_of_date,
        amount=amount,
        percentage=percentage,
        full=full
    )
    
    if exec_df.empty:
        print("⚠️ No valid withdrawal plan could be generated.")
        return
    
    withdrawal_amount = exec_df["Invested"].sum()
    
    display_execution_plan(exec_df, "withdrawal")
    print(f"\n💰 Total withdrawal: ₹{withdrawal_amount:,.2f}")
    
    _execute_orders(exec_df, broker, dry_run=dry_run)

def run_rebalance(
    top_n: int = 15, 
    band: int = 5, 
    cash_equivalent: str = "LIQUIDBEES.NS",
    rank_day: Optional[str] = None,
    dry_run: bool = False
):
    """
    Runs the weekly rebalance for Xcelerator Alpha Strategy with market regime check.
    In strong markets, rebalances the portfolio based on momentum rankings.
    In weak markets, moves portfolio to cash equivalent.
    
    Args:
        top_n (int): Target number of stocks in portfolio
        band (int): Band size for portfolio stability
        cash_equivalent (str): Symbol to use as cash equivalent
        rank_day (str, optional): Day of week for ranking (Monday, Tuesday, Wednesday, etc.).
                                 If None, uses the latest trading day for both ranking and execution.
        dry_run (bool): If True, simulates execution without placing orders
    """
    # Get trading dates - one for execution (latest) and one for ranking (specified day)
    exec_date = pd.to_datetime(get_last_trading_date())
    ranking_date = pd.to_datetime(get_ranking_date(rank_day))
    
    print(f"\n🔄 Running weekly rebalance strategy as of {exec_date.date()}...")
    if ranking_date != exec_date:
        print(f"📊 Using rankings from {ranking_date.date()} (last {rank_day or 'trading day'})")

    broker = ZerodhaBroker()
    previous_holdings = broker.get_holdings()
    held_symbols = [h["symbol"] for h in previous_holdings]

    if not held_symbols:
        print("⚠️ No current holdings found. Use `initial` command to deploy first.")
        return

    # Step 1: Get universe (filtered) and symbols for ranking
    universe = _get_filtered_universe()
    universe_symbols = [f"{s}.NS" for s in universe]

    # Step 2: Extend symbol list with held stocks and cash equivalent (for pricing)
    cash_symbol = cash_equivalent
    if not cash_symbol.endswith(".NS"):
        cash_symbol = f"{cash_symbol}.NS"
        
    price_symbols = list(set(universe_symbols + [f"{s}.NS" for s in held_symbols] + [cash_symbol])) + ["^CRSLDX"]
    
    # Get price data until exec_date (includes data needed for ranking_date as well)
    price_data = _get_latest_prices(price_symbols, exec_date)

    # Filter out non-universe prices before ranking
    price_data_for_ranking = {
        symbol: df for symbol, df in price_data.items()
        if symbol in universe_symbols or symbol == "^CRSLDX" or symbol == cash_symbol
    }

    # Step 3: Run strategy to get all needed information in one call
    recommendations, market_regime, held, new_entries, removed_stocks, _, ranked_df = run_strategy(
        price_data_for_ranking,
        ranking_date,  # Use ranking_date for strategy decisions
        held_symbols,
        top_n,
        band,
        cash_equivalent=cash_equivalent.replace(".NS", "")
    )

    # Step 4: Process recommendations based on market regime
    if market_regime == "WEAK":
        print("⚠️ Market regime is WEAK. Moving to cash equivalent position.")
        
        # Check if we already have only cash equivalent
        cash_symbol_clean = cash_equivalent.replace(".NS", "")
        is_in_cash = cash_symbol_clean in held_symbols and len(held_symbols) == 1
        
        if is_in_cash:
            print(f"✅ Already fully invested in {cash_symbol_clean}. No action needed.")
            return
            
        # Generate plan to move to cash
        exec_df = plan_move_to_cash_equivalent(
            previous_holdings=previous_holdings,
            price_data=price_data,
            as_of_date=exec_date,  # Use execution date for pricing
            ranked_df=ranked_df,
            cash_equivalent=cash_equivalent
        )
    else:
        print("💪 Market regime is STRONG. Running normal rebalance.")
        
        # Convert recommendations to the format needed for planner
        sell_symbols = [rec["symbol"] for rec in recommendations if rec["action"] == "SELL"]
        buy_symbols = [rec["symbol"] for rec in recommendations if rec["action"] == "BUY"]
        held = [sym for sym in held_symbols if sym not in sell_symbols]
        
        # No recommendations means no change needed
        if not recommendations:
            print("✅ Portfolio is already optimal. No changes needed.")
            return
            
        # Generate rebalance plan
        exec_df = plan_portfolio_rebalance(
            held_stocks=held,
            new_entries=buy_symbols,
            removed_stocks=sell_symbols,
            previous_holdings=previous_holdings,
            price_data=price_data,
            as_of_date=exec_date,  # Use execution date for pricing
            ranked_df=ranked_df
        )
    
    # Step 5: Display and confirm execution
    display_execution_plan(exec_df, "rebalance")
    _execute_orders(exec_df, broker, dry_run=dry_run)

