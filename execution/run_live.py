from data.universe_fetcher import get_universe_symbols
from logic.filters import apply_universe_filters
from data.price_fetcher import download_and_cache_prices
from datetime import timedelta
from utils.date import get_last_trading_day
from logic.strategy import run_strategy, generate_band_adjusted_portfolio
from execution.planner import generate_execution_plan
import pandas as pd
from broker.zerodha import ZerodhaBroker

def run_live_strategy(top_n: int = 15, band: int = 5, additional_capital: float = 0.0):
    """
    Executes the live rebalance logic for the current cycle.
    - Filters universe
    - Fetches price data
    - Runs strategy
    - Prints top 15 picks
    """
    
    print("\n🚀 Running live strategy...")

    # Step 1: Resolve date
    as_of_date = pd.to_datetime(get_last_trading_day())
    print(f"📆 Last Trading Day: {as_of_date.date()}")

    # Step 2: Load universe and apply filters
    universe = get_universe_symbols("nifty500")
    filtered = apply_universe_filters(universe)
    symbols = [f"{s}.NS" for s in filtered] + ["^NSEI"]

    # Step 3: Fetch price data
    start = (as_of_date - timedelta(days=400)).strftime("%Y-%m-%d")
    end = as_of_date.strftime("%Y-%m-%d")
    price_data = download_and_cache_prices(symbols, start=start, end=end)

    # Step 4: Get latest ranking
    full_ranked_df = run_strategy(price_data, as_of_date)
    top_15_df = full_ranked_df.nsmallest(15, "total_rank")
    if top_15_df.empty:
        print("💤 Market weak or no opportunities. Strategy will stay in cash.")
        return
    
    # Assign rank explicitly (1-based)
    top_15_df = top_15_df.copy()
    top_15_df["rank"] = top_15_df["total_rank"].rank(method="first").astype(int)

    # Step 5: Get live holdings from broker
    broker = ZerodhaBroker()
    broker.connect()
    live_holdings = broker.get_holdings()

    previous_holdings = [
        {
            "symbol": h["tradingsymbol"].replace(".NS", ""),
            "quantity": h["quantity"],
            "buy_price": h["average_price"]
        }
        for h in live_holdings if h["quantity"] > 0
    ]
    held_symbols = [h["symbol"] for h in previous_holdings]

    # Step 6: Apply band logic
    held, new_entries, removed, final_portfolio = generate_band_adjusted_portfolio(
        full_ranked_df, held_symbols, top_n=top_n, band=band
    )

    # Step 7: Generate execution plan
    exec_df = generate_execution_plan(
        held, new_entries, removed, previous_holdings,
        price_data, as_of_date, additional_capital, full_ranked_df
    )

    # Step 8: Display
    print("\n📦 Final Execution Plan")
    display_cols = ["Symbol", "Rank", "Action", "Price", "Quantity", "Invested", "Weight %"]
    print(exec_df[display_cols].to_string(index=False))

    # Step 9: Place orders (SELL first, then BUY)
    # for _, row in exec_df.query("Action == 'SELL'").iterrows():
    #     broker.place_market_order(row["Symbol"], row["Quantity"], transaction_type="SELL")

    # for _, row in exec_df.query("Action == 'BUY'").iterrows():
    #     broker.place_market_order(row["Symbol"], row["Quantity"], transaction_type="BUY")

