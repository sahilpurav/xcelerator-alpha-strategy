import pandas as pd
import typer
import time
from data.universe_fetcher import get_universe_symbols
from logic.filters import apply_universe_filters
from data.price_fetcher import download_and_cache_prices
from datetime import timedelta
from utils.date import get_last_trading_day
from logic.strategy import get_ranked_stocks, generate_band_adjusted_portfolio
from logic.planner import plan_rebalance_investment, plan_initial_investment, plan_top_up_investment
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

def _get_previous_holdings(broker: ZerodhaBroker) -> list[dict]:
    """
    Fetches previous holdings from the broker and formats them.
    """
    holdings = broker.get_holdings()
    return [
        {
            "symbol": h["tradingsymbol"].replace(".NS", ""),
            "quantity": h["quantity"],
            "buy_price": h["average_price"]
        }
        for h in holdings if h["quantity"] > 0
    ]

def _display_execution_plan(exec_df: pd.DataFrame, title: str):
    print(f"\n📦 {title}")
    preferred_cols = ["Symbol", "Rank", "Action", "Price", "Quantity", "Invested", "Weight %"]
    available_cols = [col for col in preferred_cols if col in exec_df.columns]
    print(exec_df[available_cols].to_string(index=False))

def _execute_orders(exec_df: pd.DataFrame, broker: ZerodhaBroker, dry_run: bool = False):
    """
    Executes the given execution plan using the broker API.
    SELLs are executed first, followed by BUYs.
    """

    # Ask for confirmation
    if not typer.confirm("⚠️ Do you want to proceed with live order execution?"):
        print("❎ Skipped live order execution.")
        return
    
    print("\n📡 Placing live orders via broker...")

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
                    broker.place_market_order(symbol, quantity, transaction_type=action)
                    time.sleep(1)  # Avoid hitting API rate limits
                except Exception as e:
                    print(f"❌ Failed to {action} {symbol}: {e}")

def run_initial_investment(top_n: int, amount: float):
    """
    Executes the initial investment strategy by selecting the top N ranked stocks from the filtered universe,
    allocating the specified total capital among them, and displaying the resulting execution plan.
    Args:
        top_n (int): The number of top-ranked stocks to select for investment.
        amount (float): The total capital to be allocated across the selected stocks.
    Returns:
        None
    Workflow:
        1. Retrieves the last trading day and prints it.
        2. Fetches the filtered universe of stocks and appends index symbol.
        3. Obtains the latest price data for the selected symbols.
        4. Ranks the stocks based on predefined criteria.
        5. Selects the top N stocks with the best (lowest) total rank.
        6. Generates an execution plan for initial investment allocation.
        7. Displays the execution plan to the user.
    """
    as_of_date = pd.to_datetime(get_last_trading_day())
    print(f"\n🟢 Running initial investment strategy as of {as_of_date.date()}")

    universe = _get_filtered_universe()
    symbols = [f"{s}.NS" for s in universe] + ["^NSEI"]
    price_data = _get_latest_prices(symbols, as_of_date)

    ranked_df = get_ranked_stocks(price_data, as_of_date)
    top_n_df = ranked_df.nsmallest(top_n, "total_rank")
    selected = top_n_df["symbol"].tolist()

    exec_df = plan_initial_investment(
        symbols=selected,
        price_data=price_data,
        as_of_date=as_of_date,
        total_capital=amount,
        ranked_df=ranked_df
    )

    _display_execution_plan(exec_df, "Initial Investment Plan")

    broker = ZerodhaBroker()
    _execute_orders(exec_df, broker)
    
def run_topup_only(amount: float):
    """
    Distributes new capital equally across currently held stocks.
    No ranking, no sells — just top-up.
    """
    as_of_date = pd.to_datetime(get_last_trading_day())
    print(f"\n💰 Running capital top-up strategy as of {as_of_date.date()}...")

    broker = ZerodhaBroker()
    previous_holdings = _get_previous_holdings(broker)

    if not previous_holdings:
        print("⚠️ No holdings found. Use `initial` command to start portfolio.")
        return
    
    held_symbols = [h["symbol"] for h in previous_holdings]
    symbols = [f"{s}.NS" for s in held_symbols]
    price_data = _get_latest_prices(symbols, as_of_date)
    
    exec_df = plan_top_up_investment(
        previous_holdings=previous_holdings,
        price_data=price_data,
        as_of_date=as_of_date,
        additional_capital=amount
    )

    _display_execution_plan(exec_df, "Top-Up Plan")
    _execute_orders(exec_df, broker)

def run_rebalance(band: int = 5):
    """
    Runs the weekly rebalance for Xcelerator Alpha Strategy.
    Automatically uses the number of current holdings as top_n.
    Sells stocks outside band, buys new entries using freed capital only.
    """
    as_of_date = pd.to_datetime(get_last_trading_day())
    print(f"\n🔄 Running weekly rebalance strategy as of {as_of_date.date()}...")

    broker = ZerodhaBroker()
    previous_holdings = _get_previous_holdings(broker)
    held_symbols = [h["symbol"] for h in previous_holdings]

    if not held_symbols:
        print("⚠️ No current holdings found. Use `initial` command to deploy first.")
        return

    top_n = len(held_symbols)

    # Step 1: Get universe (filtered) and symbols for ranking
    universe = _get_filtered_universe()
    universe_symbols = [f"{s}.NS" for s in universe]

    # Step 2: Extend symbol list with held stocks (for pricing)
    price_symbols = list(set(universe_symbols + [f"{s}.NS" for s in held_symbols])) + ["^NSEI"]
    price_data = _get_latest_prices(price_symbols, as_of_date)

    # Filter out non-universe prices before ranking
    price_data_for_ranking = {
        symbol: df for symbol, df in price_data.items()
        if symbol in universe_symbols or symbol == "^NSEI"
    }

    # Step 3: Get ranked DataFrame (only on filtered universe)
    ranked_df = get_ranked_stocks(price_data_for_ranking, as_of_date)

    held, new_entries, removed, _ = generate_band_adjusted_portfolio(
        ranked_df,
        held_symbols,
        top_n,
        band
    )

    # Step 6: Generate final execution plan
    exec_df = plan_rebalance_investment(
        held_stocks=held,
        new_entries=new_entries,
        removed_stocks=removed,
        previous_holdings=previous_holdings,
        price_data=price_data,
        as_of_date=as_of_date,
        ranked_df=ranked_df
    )

    # Step 7: Display and confirm execution
    _display_execution_plan(exec_df, "Rebalance Plan")
    _execute_orders(exec_df, broker)

